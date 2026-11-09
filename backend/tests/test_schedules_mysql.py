from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session
from app.models.doses import DoseEvent
from app.models.medicines import PrescriptionVersion, Prescription, WarningCheck
from app.models.identity import utcnow
from app.services.schedules import ScheduleService
from tests.test_tanjila_mysql import catalogue, item, check, confirm
from tests.test_sandip_mysql import invite, accept

pytestmark = pytest.mark.mysql


def test_confirmation_generates_unique_doses_and_refresh_extends(catalogue, db_engine):
    c, _, p, meds = catalogue
    tomorrow = utcnow().astimezone(ZoneInfo('Asia/Dhaka')).date() + timedelta(days=1)
    data = item(meds['Demo Alpha'])
    data.update(start_date=str(tomorrow), end_date=str(tomorrow + timedelta(days=1)), times_local=['08:00', '20:00'])
    review = check(c, p, [data])
    response = confirm(c, p, review)
    assert response.status_code == 200, response.text
    assert response.json()['schedule_status'] == 'generated'
    assert confirm(c, p, review).json() == response.json()
    path = f'/api/v1/patients/{p["id"]}/doses'
    rows = c.get(path).json()
    assert rows['total'] == 4
    assert rows['items'][0]['scheduled_at'].startswith(str(tomorrow) + 'T02:00:00')
    assert rows['items'][0]['quantity'] == '1.000'
    assert c.get(path + '?limit=1&offset=1').json()['items'][0]['id'] == rows['items'][1]['id']
    assert c.get(path + '?limit=101').status_code == 422
    assert c.post(path + '/refresh').status_code == 200
    assert c.get(path).json() == rows
    with Session(db_engine) as db, db.begin():
        version = db.get(PrescriptionVersion, response.json()['version_id'])
        # A horizon extension long after the inclusive end date creates no new doses.
        ScheduleService().extend_version(db, version, utcnow() + timedelta(days=30))
        assert db.scalar(select(func.count()).select_from(DoseEvent)) == 4


def test_as_needed_has_no_events(catalogue):
    c, _, p, meds = catalogue
    data = item(meds['Demo Alpha']); data.update(schedule_kind='as_needed', times_local=[])
    assert confirm(c, p, check(c, p, [data])).status_code == 200
    assert c.get(f'/api/v1/patients/{p["id"]}/doses').json()['total'] == 0


def test_generation_failure_rolls_back_confirmation(catalogue, db_engine, monkeypatch):
    c, _, p, meds = catalogue
    review = check(c, p, [item(meds['Demo Alpha'])])
    def fail(self, db, command, now):
        raise RuntimeError('Simulated schedule failure')
    monkeypatch.setattr(ScheduleService, 'regenerate', fail)
    with pytest.raises(RuntimeError, match='Simulated schedule failure'):
        confirm(c, p, review)
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(Prescription)) == 0
        assert db.scalar(select(func.count()).select_from(DoseEvent)) == 0
        assert db.get(WarningCheck, review['check_id']).confirmed_version_id is None


def test_refresh_supports_legacy_records_and_concurrent_retries(catalogue, db_engine):
    c, _, p, meds = catalogue
    version_id = confirm(c, p, check(c, p, [item(meds['Demo Alpha'])])).json()['version_id']
    with Session(db_engine) as db, db.begin():
        db.execute(delete(DoseEvent))
        db.get(PrescriptionVersion, version_id).schedule_status = 'not_integrated'
    path = f'/api/v1/patients/{p["id"]}/doses'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: c.post(path + '/refresh'), range(2)))
    assert all(r.status_code == 200 for r in results)
    rows = c.get(path).json()['items']
    assert len(rows) in (13, 14)
    assert len({r['scheduled_at'] for r in rows}) == len(rows)
    assert all(r['scheduled_at'] > utcnow().isoformat() for r in rows)
    with Session(db_engine) as db, db.begin():
        version = db.get(PrescriptionVersion, version_id)
        assert version.schedule_status == 'generated'
        ScheduleService().extend_version(db, version, utcnow() + timedelta(days=7))
        assert db.scalar(select(func.count()).select_from(DoseEvent)) == len(rows) + 7


def test_dose_permissions_and_revocation(catalogue, accounts):
    c, _, p, meds = catalogue
    confirm(c, p, check(c, p, [item(meds['Demo Alpha'])]))
    reader, reader_user = accounts('DoseReader')
    outsider, _ = accounts('Outsider')
    invitation, _ = invite((c, None, p), reader_user['email'], scopes=['medicines:read'])
    assert accept(reader, invitation).status_code == 200
    path = f'/api/v1/patients/{p["id"]}/doses'
    assert reader.get(path).status_code == 200
    assert reader.post(path + '/refresh').status_code == 403
    assert outsider.get(path).status_code == 404
    assert c.post(path + '/refresh', headers={'X-CSRF-Token': 'bad'}).status_code == 403
    members = c.get(f'/api/v1/patients/{p["id"]}/circle').json()
    member = next(m for m in members['members'] if m['user_id'] == reader_user['id'])
    assert c.delete(f'/api/v1/patients/{p["id"]}/circle/members/{member["id"]}').status_code == 204
    assert reader.get(path).status_code == 404
