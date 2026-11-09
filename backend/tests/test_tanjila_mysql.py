from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.main import app
from app.models import User, Membership
from app.models.identity import utcnow
from app.models.medicines import Medicine, PrescriptionVersion, WarningCheck
from tests.test_sandip_mysql import invite, accept

pytestmark = pytest.mark.mysql
CSV = (Path(__file__).resolve().parents[1] / 'data/medicines-demo.csv').read_text()


@pytest.fixture
def catalogue(owner, db_engine):
    client, user, patient = owner
    with Session(db_engine) as db, db.begin():
        db.get(User, user['id']).is_admin = True
    response = client.post('/api/v1/medicines/import', json={'csv_text': CSV})
    assert response.status_code == 200 and response.json()['imported'] == 4, response.text
    medicines = {m['brand_name']: m for m in client.get('/api/v1/medicines').json()['items']}
    return client, user, patient, medicines


def item(medicine, **changes):
    return dict(medicine_id=medicine['id'], quantity_per_dose='1', unit={'tablet':'tablet', 'capsule':'capsule', 'liquid':'ml'}[medicine['form']],
                start_date=utcnow().date().isoformat(), end_date=None, schedule_kind='fixed_times', times_local=['08:00'], timezone='Asia/Dhaka', **changes)


def check(client, patient, items):
    result = client.post(f'/api/v1/patients/{patient["id"]}/interaction-check', json={'items': items})
    assert result.status_code == 200, result.text
    return result.json()


def confirm(client, patient, review, ack=True):
    return client.post(f'/api/v1/patients/{patient["id"]}/prescriptions/confirm', json={
        'check_id': review['check_id'], 'acknowledged_warning_ids': [w['id'] for w in review['warnings']] if ack else []})


def test_import_atomic_errors_deduplication_and_search(catalogue):
    c, _, _, meds = catalogue
    assert c.post('/api/v1/medicines/import', json={'csv_text': CSV}).json() == {'imported':0,'duplicates':4,'errors':[]}
    bad = CSV.replace('Demo Alpha,10mg', 'New Alpha,invalid')
    result = c.post('/api/v1/medicines/import', json={'csv_text': bad}).json()
    assert result['imported'] == 0 and result['errors'][0]['row'] == 2
    assert c.get('/api/v1/medicines').json()['total'] == 4
    assert c.get('/api/v1/medicines', params={'q':'Dmo Alpha', 'strength':'10 mg', 'form':'tablet'}).json()['items'][0]['id'] == meds['Demo Alpha']['id']
    assert c.get('/api/v1/medicines', params={'q':'alpha'}).json()['total'] == 2
    assert c.get('/api/v1/medicines', params={'generic':'Demo compound alpha'}).json()['total'] == 2
    assert len(c.get('/api/v1/medicines?limit=1&offset=1').json()['items']) == 1
    assert c.get('/api/v1/medicines?limit=101').status_code == 422


def test_admin_auth_csrf_and_patient_isolation(catalogue, accounts):
    c, _, p, meds = catalogue
    other, _ = accounts('Other')
    assert other.post('/api/v1/medicines/import', json={'csv_text':CSV}).status_code == 403
    assert c.post('/api/v1/medicines/import', json={'csv_text':CSV}, headers={'X-CSRF-Token':'bad'}).status_code == 403
    for suffix in ('allergies', 'prescriptions'):
        assert other.get(f'/api/v1/patients/{p["id"]}/{suffix}').status_code == 404
    assert other.post(f'/api/v1/patients/{p["id"]}/interaction-check', json={'items':[item(meds['Demo Alpha'])]}).status_code == 404
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/v1/medicines').status_code == 401


def test_interaction_allergy_duplicate_ack_and_idempotent_confirmation(catalogue, db_engine):
    c, _, p, meds = catalogue
    a, b = meds['Demo Alpha'], meds['Demo Beta']
    rule = dict(medicine_a_id=a['id'],medicine_b_id=b['id'],severity='critical',explanation='Synthetic demonstration interaction.',source='Fictional course test rule; not clinical')
    assert c.post('/api/v1/medicines/interaction-rules',json=rule).status_code == 200
    assert c.put(f'/api/v1/patients/{p["id"]}/allergies',json={'generic_names':[' DEMO compound BETA ']}).status_code == 200
    first = check(c,p,[item(a)])
    assert first['warnings'] == []
    assert confirm(c,p,first).status_code == 200
    review = check(c,p,[item(meds['Demo Alpha Alternate']),item(b)])
    assert {w['kind'] for w in review['warnings']} == {'allergy','duplicate','interaction'}
    assert all(w['source'] and w['severity'] for w in review['warnings'])
    assert confirm(c,p,review,False).status_code == 409
    result = confirm(c,p,review)
    assert result.status_code == 200 and result.json()['schedule_status'] == 'generated'
    assert confirm(c,p,review).json() == result.json()
    with Session(db_engine) as db:
        assert db.get(WarningCheck,review['check_id']).acknowledged_at is not None
        assert db.scalar(select(func.count()).select_from(PrescriptionVersion)) == 2
    assert len(c.get(f'/api/v1/patients/{p["id"]}/prescriptions').json()['items']) == 3


@pytest.mark.parametrize('change', ['allergy','reference','medication','expiry'])
def test_stale_reviews_rejected(catalogue, db_engine, change):
    c, _, p, meds = catalogue
    review = check(c,p,[item(meds['Demo Alpha'])])
    if change == 'allergy':
        c.put(f'/api/v1/patients/{p["id"]}/allergies',json={'generic_names':['demo compound alpha']})
    elif change == 'reference':
        c.post('/api/v1/medicines/import',json={'csv_text':CSV.replace('Demo Gamma','Demo Delta')})
    elif change == 'medication':
        assert confirm(c,p,check(c,p,[item(meds['Demo Beta'])])).status_code == 200
    else:
        with Session(db_engine) as db, db.begin():
            db.get(WarningCheck,review['check_id']).expires_at = utcnow()-timedelta(seconds=1)
    assert confirm(c,p,review).status_code == 409


def test_readonly_and_revoked_caregiver(catalogue, owner, accounts, db_engine):
    c, _, p, meds = catalogue
    other, user = accounts('Reader')
    token,_ = invite(owner,user['email'],['medicines:read'])
    assert accept(other,token).status_code == 200
    assert other.get(f'/api/v1/patients/{p["id"]}/prescriptions').status_code == 200
    assert other.post(f'/api/v1/patients/{p["id"]}/interaction-check',json={'items':[item(meds['Demo Alpha'])]}).status_code == 403
    with Session(db_engine) as db, db.begin():
        db.scalar(select(Membership).where(Membership.user_id==user['id'])).revoked_at = utcnow()
    assert other.get(f'/api/v1/patients/{p["id"]}/allergies').status_code == 404


def test_invalid_items_and_unknown_medicine(catalogue):
    c,_,p,meds = catalogue
    valid = item(meds['Demo Alpha'])
    for bad in (valid | {'unit':'ml'}, valid | {'quantity_per_dose':'0'}, valid | {'times_local':['8:00']}, valid | {'medicine_id':str(uuid4())}):
        assert c.post(f'/api/v1/patients/{p["id"]}/interaction-check',json={'items':[bad]}).status_code == 422


def test_concurrent_confirmation_creates_one_version(catalogue, db_engine):
    c,_,p,meds = catalogue
    review = check(c,p,[item(meds['Demo Alpha'])])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _:confirm(c,p,review),range(2)))
    assert [r.status_code for r in results] == [200,200]
    assert results[0].json() == results[1].json()
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(PrescriptionVersion)) == 1
