"""CC-14 appointment tracker: schema validation, MySQL workflows, scopes and post-visit prompt."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointments import Appointment
from app.models.identity import AuditEvent, utcnow
from app.schemas.appointments import AppointmentCreate, AppointmentUpdate, CancelInput, CompleteInput
from tests.test_sandip_mysql import accept, invite

pytestmark = pytest.mark.mysql


# ---------------------------------------------------------------- schema validation (no DB)

def future_time(hours=48):
    return (utcnow() + timedelta(hours=hours)).isoformat().replace('+00:00', 'Z')


def valid(**changes):
    return dict(clinician_label='Dr Smith', scheduled_at=future_time(), timezone='Asia/Dhaka') | changes


def test_valid_appointment_input():
    AppointmentCreate(**valid())
    AppointmentCreate(**valid(location='Room 3', notes='Bring records',
                               checklist=[{'text': 'Bring prescription', 'done': False}]))


@pytest.mark.parametrize('changes', [
    {'clinician_label': ''},
    {'clinician_label': None},
    {'timezone': 'Not/ATimezone'},
    {'timezone': ''},
    {'checklist': [{'text': ''}]},                   # empty text
    {'checklist': [{'text': 'x'} for _ in range(21)]},   # over limit
    {'extra_field': 'bad'},                          # extra field forbidden
])
def test_invalid_inputs_rejected(changes):
    with pytest.raises(ValidationError):
        AppointmentCreate(**valid(**changes))


def test_update_requires_at_least_one_field():
    with pytest.raises(ValidationError):
        AppointmentUpdate()


# ---------------------------------------------------------------- helpers

def path(patient):
    return f'/api/v1/patients/{patient["id"]}'


def create(client, patient, **overrides):
    body = dict(clinician_label='Dr Smith', scheduled_at=future_time(), timezone='Asia/Dhaka') | overrides
    return client.post(f'{path(patient)}/appointments', json=body)


def appt_count(db_engine, patient_id):
    with Session(db_engine) as db:
        return db.scalar(select(func.count()).select_from(Appointment).where(Appointment.patient_id == patient_id))


# ---------------------------------------------------------------- MySQL workflows

def test_create_list_get_and_filter(owner):
    client, _, patient = owner
    r1 = create(client, patient, clinician_label='Dr A', timezone='Asia/Dhaka')
    assert r1.status_code == 201
    body = r1.json()
    assert body['status'] == 'scheduled'
    assert body['clinician_label'] == 'Dr A'
    assert 'scheduled_local' in body
    assert body['checklist'] == {'items': []}
    r2 = create(client, patient, clinician_label='Dr B', timezone='Asia/Dhaka')
    assert r2.status_code == 201
    listing = client.get(f'{path(patient)}/appointments').json()
    assert listing['total'] == 2
    single = client.get(f'{path(patient)}/appointments/{body["id"]}').json()
    assert single['id'] == body['id']
    filtered = client.get(f'{path(patient)}/appointments?status=scheduled').json()
    assert filtered['total'] == 2
    client.post(f'{path(patient)}/appointments/{r2.json()["id"]}/cancel', json={})
    assert client.get(f'{path(patient)}/appointments?status=cancelled').json()['total'] == 1
    assert client.get(f'{path(patient)}/appointments?status=scheduled').json()['total'] == 1


def test_update_scheduled_appointment(owner):
    client, _, patient = owner
    appt = create(client, patient).json()
    r = client.patch(f'{path(patient)}/appointments/{appt["id"]}', json={'clinician_label': 'Dr Updated', 'notes': 'New notes'})
    assert r.status_code == 200
    assert r.json()['clinician_label'] == 'Dr Updated'
    assert r.json()['notes'] == 'New notes'


def test_cannot_edit_cancelled_or_completed_appointment(owner):
    client, _, patient = owner
    appt = create(client, patient).json()
    client.post(f'{path(patient)}/appointments/{appt["id"]}/cancel', json={})
    r = client.patch(f'{path(patient)}/appointments/{appt["id"]}', json={'clinician_label': 'Changed'})
    assert r.status_code == 409
    appt2 = create(client, patient).json()
    client.post(f'{path(patient)}/appointments/{appt2["id"]}/complete', json={'post_visit_prompt': False})
    assert client.patch(f'{path(patient)}/appointments/{appt2["id"]}', json={'clinician_label': 'Changed'}).status_code == 409


def test_checklist_with_items_and_per_item_toggle(owner):
    client, _, patient = owner
    appt = create(client, patient, checklist=[
        {'text': 'Bring prescriptions', 'done': False},
        {'text': 'List symptoms', 'done': False},
    ]).json()
    assert appt['checklist']['items'][0]['done'] is False
    r = client.patch(f'{path(patient)}/appointments/{appt["id"]}/checklist/0?done=true')
    assert r.status_code == 200
    assert r.json()['checklist']['items'][0]['done'] is True
    assert r.json()['checklist']['items'][1]['done'] is False
    assert client.patch(f'{path(patient)}/appointments/{appt["id"]}/checklist/99?done=true').status_code == 404


def test_complete_sets_status_and_post_visit_prompt(owner, db_engine):
    client, _, patient = owner
    appt = create(client, patient).json()
    r = client.post(f'{path(patient)}/appointments/{appt["id"]}/complete', json={'post_visit_prompt': True})
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'completed'
    assert body['completed_at'] is not None
    assert body['post_visit_prompt_at'] is not None
    assert body['post_visit_dismissed_at'] is None
    with Session(db_engine) as db:
        row = db.get(Appointment, appt['id'])
        assert row.status == 'completed'


def test_complete_without_post_visit_prompt(owner):
    client, _, patient = owner
    appt = create(client, patient).json()
    r = client.post(f'{path(patient)}/appointments/{appt["id"]}/complete', json={'post_visit_prompt': False})
    assert r.json()['post_visit_prompt_at'] is None


def test_cancel_sets_status_and_reason(owner, db_engine):
    client, _, patient = owner
    appt = create(client, patient).json()
    r = client.post(f'{path(patient)}/appointments/{appt["id"]}/cancel', json={'reason': 'Patient unavailable'})
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'cancelled'
    assert body['cancelled_reason'] == 'Patient unavailable'
    assert body['cancelled_at'] is not None


def test_cancel_without_reason_is_allowed(owner):
    client, _, patient = owner
    appt = create(client, patient).json()
    r = client.post(f'{path(patient)}/appointments/{appt["id"]}/cancel', json={})
    assert r.status_code == 200 and r.json()['cancelled_reason'] is None


def test_cannot_cancel_already_cancelled_or_completed(owner):
    client, _, patient = owner
    appt = create(client, patient).json()
    client.post(f'{path(patient)}/appointments/{appt["id"]}/cancel', json={})
    assert client.post(f'{path(patient)}/appointments/{appt["id"]}/cancel', json={}).status_code == 409
    appt2 = create(client, patient).json()
    client.post(f'{path(patient)}/appointments/{appt2["id"]}/complete', json={'post_visit_prompt': False})
    assert client.post(f'{path(patient)}/appointments/{appt2["id"]}/cancel', json={}).status_code == 409


def test_cannot_complete_cancelled_appointment(owner):
    client, _, patient = owner
    appt = create(client, patient).json()
    client.post(f'{path(patient)}/appointments/{appt["id"]}/cancel', json={})
    assert client.post(f'{path(patient)}/appointments/{appt["id"]}/complete', json={'post_visit_prompt': False}).status_code == 409


def test_dismiss_post_visit_prompt(owner):
    client, _, patient = owner
    appt = create(client, patient).json()
    client.post(f'{path(patient)}/appointments/{appt["id"]}/complete', json={'post_visit_prompt': True})
    r = client.post(f'{path(patient)}/appointments/{appt["id"]}/dismiss-prompt', json={})
    assert r.status_code == 200
    assert r.json()['post_visit_dismissed_at'] is not None
    assert client.post(f'{path(patient)}/appointments/{appt["id"]}/dismiss-prompt', json={}).status_code == 409


def test_dismiss_prompt_on_no_prompt_appointment(owner):
    client, _, patient = owner
    appt = create(client, patient).json()
    client.post(f'{path(patient)}/appointments/{appt["id"]}/complete', json={'post_visit_prompt': False})
    assert client.post(f'{path(patient)}/appointments/{appt["id"]}/dismiss-prompt', json={}).status_code == 404


def test_past_appointment_rejected(owner, db_engine):
    client, _, patient = owner
    past = (utcnow() - timedelta(hours=2)).isoformat().replace('+00:00', 'Z')
    r = create(client, patient, scheduled_at=past)
    assert r.status_code == 422
    assert appt_count(db_engine, patient['id']) == 0


def test_invalid_status_filter(owner):
    client, _, patient = owner
    assert client.get(f'{path(patient)}/appointments?status=invalid').status_code == 422


def test_pagination(owner):
    client, _, patient = owner
    for i in range(5):
        create(client, patient, clinician_label=f'Dr {i}',
               scheduled_at=(utcnow() + timedelta(hours=i+2)).isoformat().replace('+00:00', 'Z'))
    assert client.get(f'{path(patient)}/appointments?limit=2&offset=0').json()['total'] == 5
    assert len(client.get(f'{path(patient)}/appointments?limit=2&offset=0').json()['items']) == 2
    assert len(client.get(f'{path(patient)}/appointments?limit=2&offset=4').json()['items']) == 1
    assert client.get(f'{path(patient)}/appointments?limit=101').status_code == 422


def test_scopes_read_write_unscoped_stranger_revoked(owner, accounts, db_engine):
    client, _, patient = owner
    reader, reader_user = accounts('Reader')
    writer, writer_user = accounts('Writer')
    blind, blind_user = accounts('Blind')
    stranger, _ = accounts('Stranger')
    accept(reader, invite(owner, reader_user['email'], ['appointments:read'])[0])
    accept(writer, invite(owner, writer_user['email'], ['appointments:write'])[0])
    accept(blind, invite(owner, blind_user['email'], ['medicines:read'])[0])
    create(client, patient)
    base = path(patient)
    assert reader.get(f'{base}/appointments').status_code == 200
    assert create(reader, patient).status_code == 403
    assert writer.get(f'{base}/appointments').status_code == 200
    assert create(writer, patient).status_code == 201
    assert blind.get(f'{base}/appointments').status_code == 403
    assert stranger.get(f'{base}/appointments').status_code == 404
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as anon:
        assert anon.get(f'{base}/appointments').status_code == 401
    members = client.get(f'{base}/circle').json()['members']
    member = next(m for m in members if m['email'] == writer_user['email'])
    client.delete(f'{base}/circle/members/{member["id"]}')
    assert writer.get(f'{base}/appointments').status_code == 404
    assert create(writer, patient).status_code == 404


def test_patients_isolated_from_each_other(owner, accounts):
    client, _, patient = owner
    other, _ = accounts('Other')
    other_patient = other.post('/api/v1/patients', json=dict(
        display_name='Other', timezone='Asia/Dhaka', kind='self', consent=True,
        consent_basis='I consent to this synthetic test.')).json()
    create(client, patient, clinician_label='Mine')
    create(other, other_patient, clinician_label='Theirs')
    mine = client.get(f'{path(patient)}/appointments').json()['items']
    theirs = other.get(f'{path(other_patient)}/appointments').json()['items']
    assert [a['clinician_label'] for a in mine] == ['Mine']
    assert [a['clinician_label'] for a in theirs] == ['Theirs']
    assert other.get(f'{path(patient)}/appointments').status_code == 404


def test_audit_records_create_complete_cancel(owner, db_engine):
    client, user, patient = owner
    appt = create(client, patient).json()
    client.post(f'{path(patient)}/appointments/{appt["id"]}/complete', json={'post_visit_prompt': True})
    appt2 = create(client, patient).json()
    client.post(f'{path(patient)}/appointments/{appt2["id"]}/cancel', json={'reason': 'Test'})
    with Session(db_engine) as db:
        events = db.scalars(select(AuditEvent).where(AuditEvent.patient_id == patient['id'])).all()
        actions = {e.action for e in events}
        assert {'appointment.created', 'appointment.completed', 'appointment.cancelled'} <= actions
        for e in events:
            assert e.actor_user_id == user['id']


def test_csrf_enforced_on_writes(owner):
    client, _, patient = owner
    body = dict(clinician_label='Dr X', scheduled_at=future_time(), timezone='Asia/Dhaka')
    assert client.post(f'{path(patient)}/appointments', json=body, headers={'X-CSRF-Token': 'bad'}).status_code == 403
    assert client.post(f'{path(patient)}/appointments', json=body, headers={'Origin': 'https://evil.example'}).status_code == 403


def test_concurrent_creates_all_succeed(owner, db_engine):
    client, _, patient = owner
    body = dict(clinician_label='Dr Concurrent', scheduled_at=future_time(), timezone='Asia/Dhaka')
    with ThreadPoolExecutor(4) as pool:
        codes = sorted(pool.map(lambda i: client.post(f'{path(patient)}/appointments',
                                                       json=body | {'clinician_label': f'Dr {i}'}).status_code, range(4)))
    assert codes == [201, 201, 201, 201]
    assert appt_count(db_engine, patient['id']) == 4


def test_get_nonexistent_appointment_returns_404(owner):
    client, _, patient = owner
    from uuid import uuid4
    assert client.get(f'{path(patient)}/appointments/{uuid4()}').status_code == 404
