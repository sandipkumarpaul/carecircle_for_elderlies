from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import io
import subprocess
import pytest
from PIL import Image
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models import Alert, AlertRecipient, Membership
from app.models.doses import DoseEvent
from app.models.identity import utcnow
from app.models.medicines import PrescriptionVersion, PrescriptionItem, OcrDraft
from app.services.schedules import ScheduleService
from app.services import ocr
from tests.test_tanjila_mysql import catalogue, item, check, confirm
from tests.test_sandip_mysql import invite, accept

pytestmark = pytest.mark.mysql


def proposed(med, quantity='1'):
    data = item(med)
    data.update(start_date=str(utcnow().date() + timedelta(days=1)), quantity_per_dose=quantity, times_local=['08:00','20:00'])
    return data


def revision(c, p, version, items):
    result = c.post(f'/api/v1/patients/{p["id"]}/interaction-check', json=dict(items=items, replaces_version_id=version,
        change_reason='Recorded updated clinician instruction'))
    assert result.status_code == 200, result.text
    return result.json()


def test_revision_preserves_history_and_completed_doses_and_notifies(catalogue, accounts, db_engine):
    c, _, p, meds = catalogue
    caregiver, user = accounts('RevisionCaregiver')
    token, _ = invite((c,None,p), user['email'], ['medicines:read','alerts:read']); accept(caregiver,token)
    old = confirm(c,p,check(c,p,[proposed(meds['Demo Alpha'])])).json()['version_id']
    with Session(db_engine) as db, db.begin():
        original = db.scalar(select(PrescriptionItem).where(PrescriptionItem.prescription_version_id == old))
        original_id, original_quantity = original.id, original.quantity_per_dose
        doses = db.scalars(select(DoseEvent).order_by(DoseEvent.scheduled_at)).all()
        doses[0].status = 'taken'; kept = doses[0].id
        doses[1].scheduled_at = utcnow() - timedelta(days=1); elapsed = doses[1].id
    review = revision(c,p,old,[proposed(meds['Demo Alpha'],'2')])
    assert review['warnings'] == []  # Replaced version must not warn against itself.
    result = confirm(c,p,review)
    assert result.status_code == 200, result.text
    assert confirm(c,p,review).json() == result.json()
    with Session(db_engine) as db:
        assert db.get(PrescriptionItem,original_id).quantity_per_dose == original_quantity
        assert db.get(DoseEvent,kept).status == 'taken'
        assert db.get(DoseEvent,elapsed).status == 'pending'
        assert db.get(PrescriptionVersion,old).effective_until is not None
        assert db.get(PrescriptionVersion,result.json()['version_id']).version_number == 2
        old_events = db.scalars(select(DoseEvent).where(DoseEvent.prescription_item_id == original_id, DoseEvent.id.not_in([kept,elapsed]))).all()
        assert all(d.status == 'cancelled' for d in old_events)
        assert db.scalar(select(func.count()).select_from(Alert).where(Alert.type == 'prescription_changed')) == 1
    assert caregiver.get(f'/api/v1/patients/{p["id"]}/alerts').json()['total'] == 1
    history = c.get(f'/api/v1/patients/{p["id"]}/prescription-history').json()
    assert history['total'] == 2 and history['items'][0]['version_number'] == 2
    assert history['items'][1]['items'][0]['quantity_per_dose'] == '1.000'


def test_stale_concurrent_revision_and_stop(catalogue, db_engine):
    c, _, p, meds = catalogue
    old = confirm(c,p,check(c,p,[proposed(meds['Demo Alpha'])])).json()['version_id']
    reviews = [revision(c,p,old,[proposed(meds['Demo Alpha'], q)]) for q in ('2','3')]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda r: confirm(c,p,r), reviews))
    assert sorted(r.status_code for r in results) == [200,409]
    new_id = next(r.json()['version_id'] for r in results if r.status_code == 200)
    with Session(db_engine) as db:
        root = db.get(PrescriptionVersion,new_id).prescription_id
    stale = revision(c,p,new_id,[proposed(meds['Demo Alpha'],'4')])
    path = f'/api/v1/patients/{p["id"]}/prescriptions/{root}/stop'
    data = dict(expected_version_id=new_id, reason='Clinician stopped this medicine')
    stopped = c.post(path,json=data)
    assert stopped.status_code == 200, stopped.text
    assert c.post(path,json=data).json() == stopped.json()
    assert confirm(c,p,stale).status_code == 409
    assert c.get(f'/api/v1/patients/{p["id"]}/prescriptions').json()['items'] == []
    assert c.get(f'/api/v1/patients/{p["id"]}/doses').json()['total'] == 0
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(PrescriptionVersion)) == 3


@pytest.mark.parametrize('action',['revision','stop'])
def test_regeneration_failure_rolls_back_revision_and_stop(catalogue, db_engine, monkeypatch, action):
    c, _, p, meds = catalogue
    old = confirm(c,p,check(c,p,[proposed(meds['Demo Alpha'])])).json()['version_id']
    with Session(db_engine) as db:
        root = db.get(PrescriptionVersion,old).prescription_id
    review = revision(c,p,old,[proposed(meds['Demo Alpha'],'2')])
    def fail(*args, **kwargs):
        raise RuntimeError('forced scheduling failure')
    monkeypatch.setattr(ScheduleService,'regenerate',fail)
    with pytest.raises(RuntimeError,match='forced scheduling failure'):
        if action == 'revision':
            confirm(c,p,review)
        else:
            c.post(f'/api/v1/patients/{p["id"]}/prescriptions/{root}/stop',json=dict(expected_version_id=old,reason='Recorded stop instruction'))
    with Session(db_engine) as db:
        assert db.get(PrescriptionVersion,old).effective_until is None
        assert db.scalar(select(func.count()).select_from(PrescriptionVersion)) == 1
        assert set(db.scalars(select(DoseEvent.status))) == {'pending'}
        assert db.scalar(select(func.count()).select_from(Alert)) == 0


def test_revision_authorization_and_other_prescription_warnings(catalogue, accounts):
    c, _, p, meds = catalogue
    old = confirm(c,p,check(c,p,[proposed(meds['Demo Alpha'])])).json()['version_id']
    confirm(c,p,check(c,p,[proposed(meds['Demo Alpha Alternate'])]))
    review = revision(c,p,old,[proposed(meds['Demo Alpha'],'2')])
    assert 'duplicate' in {w['kind'] for w in review['warnings']}
    assert confirm(c,p,review,False).status_code == 409
    reader, user = accounts('Reader'); token, _ = invite((c,None,p),user['email'],['medicines:read']); accept(reader,token)
    outsider, _ = accounts('Outsider')
    history = f'/api/v1/patients/{p["id"]}/prescription-history'
    assert reader.get(history).status_code == 200
    assert outsider.get(history).status_code == 404
    payload = dict(items=[proposed(meds['Demo Alpha'])],replaces_version_id=old,change_reason='Recorded instruction')
    assert reader.post(f'/api/v1/patients/{p["id"]}/interaction-check',json=payload).status_code == 403
    assert outsider.post(f'/api/v1/patients/{p["id"]}/interaction-check',json=payload).status_code == 404
    payload['replaces_version_id']=str(uuid4())
    assert c.post(f'/api/v1/patients/{p["id"]}/interaction-check',json=payload).status_code == 404


def image_bytes():
    buffer = io.BytesIO(); Image.new('RGB',(100,100),'white').save(buffer,format='PNG'); return buffer.getvalue()


def test_real_ocr_review_and_catalogue_suggestions(catalogue):
    c, _, p, meds = catalogue
    content = (Path(__file__).resolve().parents[1]/'data/prescription-demo.png').read_bytes()
    path=f'/api/v1/patients/{p["id"]}/ocr'
    result=c.post(path,content=content,headers={'Content-Type':'image/png'})
    assert result.status_code==201,result.text
    draft=result.json()
    assert 'Demo Alpha' in draft['raw_text']
    assert meds['Demo Alpha']['id'] in [s['medicine']['id'] for s in draft['suggestions']]
    assert draft['reviewed_at'] is None
    payload=dict(items=[proposed(meds['Demo Alpha'])],ocr_draft_id=draft['id'])
    assert c.post(f'/api/v1/patients/{p["id"]}/interaction-check',json=payload).status_code==409
    corrected=c.put(path+'/'+draft['id'],json=dict(reviewed_text='Demo Alpha 10mg tablet. Verified against printed prescription.',expected_revision=0))
    assert corrected.status_code==200 and corrected.json()['reviewed_at']
    assert c.get(path+'/'+draft['id']).json()['reviewed_text'].startswith('Demo Alpha')
    review=c.post(f'/api/v1/patients/{p["id"]}/interaction-check',json=payload).json()
    assert confirm(c,p,review).status_code==200
    assert c.get(f'/api/v1/patients/{p["id"]}/prescription-history').json()['items'][0]['ocr_draft_id']==draft['id']
    assert c.put(path+'/'+draft['id'],json=dict(reviewed_text='Stale edit',expected_revision=0)).status_code==409


def test_ocr_invalid_oversized_and_unauthorized(catalogue,accounts):
    c, _, p, _=catalogue; other,_=accounts('Other')
    reader,user=accounts('Reader'); token,_=invite((c,None,p),user['email'],['medicines:read']); accept(reader,token)
    path=f'/api/v1/patients/{p["id"]}/ocr'
    assert other.post(path,content=image_bytes(),headers={'Content-Type':'image/png'}).status_code==404
    assert reader.post(path,content=image_bytes(),headers={'Content-Type':'image/png'}).status_code==403
    assert c.post(path,content=b'not image',headers={'Content-Type':'image/png'}).status_code==422
    assert c.post(path,content=b'pdf',headers={'Content-Type':'application/pdf'}).status_code==415
    assert c.post(path,content=b'x'*(ocr.MAX_UPLOAD+1),headers={'Content-Type':'image/png'}).status_code==413
    assert c.post(path,content=image_bytes(),headers={'Content-Type':'image/png','X-CSRF-Token':'invalid'}).status_code==403


def test_blank_ocr_and_manual_correction(catalogue):
    c,_,p,_=catalogue; path=f'/api/v1/patients/{p["id"]}/ocr'
    result=c.post(path,content=image_bytes(),headers={'Content-Type':'image/png'})
    assert result.status_code==201,result.text
    assert result.json()['recognition_status']=='no_text'
    draft=result.json()['id']
    assert c.put(path+'/'+draft,json=dict(reviewed_text='Manual transcription: Demo Alpha',expected_revision=0)).status_code==200


@pytest.mark.parametrize('failure,status',[(FileNotFoundError(),503),(subprocess.TimeoutExpired('tesseract',25),504)])
def test_ocr_unavailable_timeout_has_no_draft(catalogue,db_engine,monkeypatch,failure,status):
    c,_,p,_=catalogue
    def fail(*args,**kwargs): raise failure
    monkeypatch.setattr(ocr.subprocess,'run',fail)
    result=c.post(f'/api/v1/patients/{p["id"]}/ocr',content=image_bytes(),headers={'Content-Type':'image/png'})
    assert result.status_code==status
    with Session(db_engine) as db: assert db.scalar(select(func.count()).select_from(OcrDraft))==0


def test_ocr_review_change_invalidates_warning_check(catalogue,monkeypatch):
    c,_,p,meds=catalogue
    monkeypatch.setattr(ocr,'extract',lambda content:dict(text='Demo Alpha',confidence=40,status='low_confidence'))
    path=f'/api/v1/patients/{p["id"]}/ocr'
    draft=c.post(path,content=image_bytes(),headers={'Content-Type':'image/png'}).json()
    c.put(path+'/'+draft['id'],json=dict(reviewed_text='Demo Alpha',expected_revision=0))
    review=c.post(f'/api/v1/patients/{p["id"]}/interaction-check',json=dict(items=[proposed(meds['Demo Alpha'])],ocr_draft_id=draft['id'])).json()
    c.put(path+'/'+draft['id'],json=dict(reviewed_text='Corrected Demo Alpha instructions',expected_revision=1))
    assert confirm(c,p,review).status_code==409


def test_revocation_during_ocr_discards_result(catalogue,accounts,db_engine,monkeypatch):
    c,_,p,_=catalogue
    caregiver,user=accounts('OcrCaregiver'); token,_=invite((c,None,p),user['email'],['medicines:write']); accept(caregiver,token)
    def recognize(content):
        with Session(db_engine) as db,db.begin():
            member=db.scalar(select(Membership).where(Membership.patient_id==p['id'],Membership.user_id==user['id']))
            member.revoked_at=utcnow()
        return dict(text='Demo Alpha',confidence=90,status='recognized')
    monkeypatch.setattr(ocr,'extract',recognize)
    result=caregiver.post(f'/api/v1/patients/{p["id"]}/ocr',content=image_bytes(),headers={'Content-Type':'image/png'})
    assert result.status_code==404
    with Session(db_engine) as db: assert db.scalar(select(func.count()).select_from(OcrDraft))==0


def test_ocr_draft_cross_patient_isolation(catalogue,accounts,monkeypatch):
    c,_,p,meds=catalogue
    monkeypatch.setattr(ocr,'extract',lambda content:dict(text='Demo Alpha',confidence=90,status='recognized'))
    original=f'/api/v1/patients/{p["id"]}/ocr'
    draft=c.post(original,content=image_bytes(),headers={'Content-Type':'image/png'}).json()['id']
    other,_=accounts('OtherDraft')
    other_patient=other.post('/api/v1/patients',json=dict(display_name='Other',timezone='UTC',kind='self',consent=True,consent_basis='Synthetic test consent')).json()
    path=f'/api/v1/patients/{other_patient["id"]}/ocr/{draft}'
    assert other.get(path).status_code==404
    assert other.put(path,json=dict(reviewed_text='Changed',expected_revision=0)).status_code==404
    assert other.post(f'/api/v1/patients/{other_patient["id"]}/interaction-check',json=dict(items=[proposed(meds['Demo Alpha'])],ocr_draft_id=draft)).status_code==404


def test_stop_permission_and_csrf(catalogue,accounts,db_engine):
    c,_,p,meds=catalogue
    old=confirm(c,p,check(c,p,[proposed(meds['Demo Alpha'])])).json()['version_id']
    with Session(db_engine) as db: root=db.get(PrescriptionVersion,old).prescription_id
    reader,user=accounts('StopReader'); token,_=invite((c,None,p),user['email'],['medicines:read']); accept(reader,token)
    path=f'/api/v1/patients/{p["id"]}/prescriptions/{root}/stop'
    payload=dict(expected_version_id=old,reason='Recorded instruction')
    assert reader.post(path,json=payload).status_code==403
    assert c.post(path,json=payload,headers={'X-CSRF-Token':'bad'}).status_code==403
    assert c.get(f'/api/v1/patients/{p["id"]}/prescription-history').json()['total']==1
