from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import SESSION_COOKIE, digest
from app.main import app
from app.models import Alert, AlertRecipient, AuthSession, AuditEvent, Delivery, Invite, Membership, User
from app.models.identity import utcnow
from app.schemas.contracts import RaiseAlertCommand, Scope
from app.services.access import permissions
from app.services.alerts import AlertService

pytestmark = pytest.mark.mysql


def invite(owner, email, scopes=None, role='secondary'):
    client, _, patient = owner
    result = client.post(f'/api/v1/patients/{patient["id"]}/circle/invites', json=dict(
        email=email, scopes=scopes or [], role=role, consent=True, expires_in_hours=48))
    assert result.status_code == 201, result.text
    data = result.json()
    return data['invite_url'].split('#invite=')[1], data['id']


def accept(client, token):
    return client.post('/api/v1/circle/invites/accept', json={'token': token, 'consent': True})


def test_auth_password_cookie_csrf_and_revocation(owner, db_engine):
    client, user, _ = owner
    original = client.cookies.get(SESSION_COOKIE)
    with Session(db_engine) as db:
        row = db.get(User, user['id'])
        assert row.password_hash.startswith('$argon2id$')
        assert 'Correct-demo' not in row.password_hash
    assert client.get('/api/v1/auth/me').status_code == 200
    assert client.post('/api/v1/auth/logout', headers={'X-CSRF-Token': 'invalid'}).status_code == 403
    assert client.post('/api/v1/auth/logout', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.post('/api/v1/auth/logout').status_code == 204
    client.cookies.set(SESSION_COOKIE, original, path='/api')
    assert client.get('/api/v1/auth/me').status_code == 401


def test_login_wrong_password_and_success(accounts):
    client, user = accounts('Login')
    assert client.post('/api/v1/auth/logout').status_code == 204
    token = client.get('/api/v1/auth/csrf').json()['csrf_token']
    client.headers['X-CSRF-Token'] = token
    assert client.post('/api/v1/auth/login', json={'email': user['email'], 'password': 'wrong'}).status_code == 401
    response = client.post('/api/v1/auth/login', json={'email': user['email'], 'password': 'Correct-demo-password-123'})
    assert response.status_code == 200
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=lax' in response.headers['set-cookie']
    assert response.json()['csrf_token'] != token


def test_rate_limit_survives_failed_login(accounts):
    client, user = accounts('Rate')
    client.post('/api/v1/auth/logout')
    client.headers['X-CSRF-Token'] = client.get('/api/v1/auth/csrf').json()['csrf_token']
    codes = [client.post('/api/v1/auth/login', json={'email': user['email'], 'password': 'wrong'}).status_code for _ in range(11)]
    assert codes[0] == 401 and codes[-1] == 429


def test_consent_profile_validation_and_self_uniqueness(owner):
    client, _, _ = owner
    data = dict(display_name='Demo', kind='self', consent=True, consent_basis='I consent to this profile.')
    assert client.post('/api/v1/patients', json=data).status_code == 409
    assert client.post('/api/v1/patients', json=data | {'kind': 'dependent', 'consent': False}).status_code == 422
    assert client.post('/api/v1/patients', json=data | {'kind': 'dependent', 'timezone': 'bad/zone'}).status_code == 422
    response = client.post('/api/v1/patients', json=data | {'kind': 'dependent'})
    assert response.status_code == 201 and response.json()['role'] == 'primary'


def test_private_list_detail_and_circle_are_isolated(owner, accounts, db_engine):
    _, _, patient = owner
    stranger, user = accounts('Stranger')
    # Even a reference admin has no implicit patient-data access.
    with Session(db_engine) as db, db.begin():
        db.get(User, user['id']).is_admin = True
    assert stranger.get('/api/v1/patients').json()['items'] == []
    assert stranger.get(f'/api/v1/patients/{patient["id"]}').status_code == 404
    assert stranger.get(f'/api/v1/patients/{patient["id"]}/circle').status_code == 404
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/v1/patients').status_code == 401


def test_invite_is_email_bound_single_use_and_hash_only(owner, accounts, db_engine):
    caregiver, user = accounts('Caregiver'); stranger, _ = accounts('Other')
    token, invite_id = invite(owner, user['email'], ['medicines:read'])
    assert stranger.post('/api/v1/circle/invites/preview', json={'token': token}).status_code == 404
    assert accept(stranger, token).status_code == 404
    assert accept(caregiver, token).status_code == 200
    assert accept(caregiver, token).status_code == 409
    patient = caregiver.get('/api/v1/patients').json()['items'][0]
    assert patient['scopes'] == ['medicines:read']
    assert caregiver.get(f'/api/v1/patients/{patient["id"]}/circle').status_code == 403
    with Session(db_engine) as db:
        assert db.get(Invite, invite_id).token_hash == digest(token)
        assert token not in str(db.get(Invite, invite_id).__dict__)
        assert db.scalar(select(func.count()).select_from(AuditEvent)) >= 3


@pytest.mark.parametrize('reason', ['expired', 'revoked'])
def test_unusable_invitation_denied(owner, accounts, db_engine, reason):
    client, user = accounts('Invitee'); token, invite_id = invite(owner, user['email'])
    if reason == 'expired':
        with Session(db_engine) as db, db.begin():
            db.get(Invite, invite_id).expires_at = utcnow() - timedelta(seconds=1)
    else:
        assert owner[0].delete(f'/api/v1/patients/{owner[2]["id"]}/circle/invites/{invite_id}').status_code == 204
    assert accept(client, token).status_code == 409


def test_primary_scope_limits_and_second_primary_conflict(owner, accounts):
    primary, primary_user = accounts('Primary'); other, other_user = accounts('Other')
    token, _ = invite(owner, primary_user['email'], ['circle:manage', 'medicines:read'], 'primary')
    assert accept(primary, token).status_code == 200
    route = f'/api/v1/patients/{owner[2]["id"]}/circle/invites'
    data = dict(email=other_user['email'], scopes=['vitals:read'], role='secondary', consent=True)
    assert primary.post(route, json=data).status_code == 403
    assert primary.post(route, json=data | {'role': 'primary', 'scopes': ['circle:manage']}).status_code == 403
    assert owner[0].post(route, json=data | {'role': 'primary', 'scopes': ['circle:manage']}).status_code == 409
    assert primary.post(route, json=data | {'scopes': ['medicines:read']}).status_code == 201


def test_permissions_change_and_revocation_apply_immediately(owner, accounts, db_engine):
    caregiver, user = accounts('Caregiver'); token, _ = invite(owner, user['email'], ['medicines:write'])
    assert accept(caregiver, token).status_code == 200
    pid = owner[2]['id']; route = f'/api/v1/patients/{pid}/circle'
    member = owner[0].get(route).json()['members'][0]
    with Session(db_engine) as db:
        permissions.require(db, user['id'], pid, Scope.MEDICINES_READ)
        with pytest.raises(HTTPException): permissions.require(db, user['id'], pid, Scope.VITALS_READ)
    assert owner[0].patch(f'{route}/members/{member["id"]}', json={'role': 'secondary', 'scopes': ['vitals:read']}).status_code == 200
    assert caregiver.get(f'/api/v1/patients/{pid}').json()['scopes'] == ['vitals:read']
    assert owner[0].delete(f'{route}/members/{member["id"]}').status_code == 204
    assert caregiver.get(f'/api/v1/patients/{pid}').status_code == 404
    assert caregiver.get('/api/v1/patients').json()['items'] == []
    with Session(db_engine) as db:
        with pytest.raises(HTTPException): permissions.require(db, user['id'], pid, Scope.VITALS_READ)


def test_revoked_inviter_cannot_leave_pending_privileged_links(owner, accounts):
    primary, puser = accounts('Primary'); invitee, iuser = accounts('Invitee')
    token, _ = invite(owner, puser['email'], ['circle:manage', 'medicines:read'], 'primary')
    accept(primary, token)
    pid = owner[2]['id']; route = f'/api/v1/patients/{pid}/circle'
    pending = primary.post(route + '/invites', json=dict(email=iuser['email'], role='secondary', scopes=['medicines:read'], consent=True)).json()
    member = owner[0].get(route).json()['members'][0]
    owner[0].delete(route + '/members/' + member['id'])
    assert accept(invitee, pending['invite_url'].split('#invite=')[1]).status_code == 409


def test_cross_patient_member_mutation_fails(owner, accounts):
    caregiver, user = accounts('Caregiver'); token, _ = invite(owner, user['email']); accept(caregiver, token)
    pid = owner[2]['id']; member = owner[0].get(f'/api/v1/patients/{pid}/circle').json()['members'][0]
    other = owner[0].post('/api/v1/patients', json=dict(display_name='Other dependent', kind='dependent', consent=True, consent_basis='Authorized synthetic representation.')).json()
    assert owner[0].delete(f'/api/v1/patients/{other["id"]}/circle/members/{member["id"]}').status_code == 404


def test_simultaneous_invitation_acceptance_has_one_winner(owner, accounts):
    caregiver, user = accounts('Race'); token, _ = invite(owner, user['email'])
    def run(_):
        with TestClient(app) as client:
            client.cookies.update(caregiver.cookies)
            client.headers.update(dict(caregiver.headers))
            return accept(client, token).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert sorted(results) == [200, 409]


def test_alert_deduplication_scope_filter_and_revoked_delivery(owner, accounts, db_engine):
    caregiver, user = accounts('Caregiver'); token, _ = invite(owner, user['email'], ['alerts:read', 'vitals:read']); accept(caregiver, token)
    limited, limited_user = accounts('Limited'); token, _ = invite(owner, limited_user['email'], ['alerts:read']); accept(limited, token)
    pid = owner[2]['id']; source = uuid4()
    command = RaiseAlertCommand(patient_id=pid, type='vital_threshold', severity='warning', source_type='vital', source_id=source, dedupe_key=f'vital:{source}')
    service = AlertService()
    def create(_):
        with Session(db_engine) as db, db.begin(): return service.raise_alert(db, command, utcnow())
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(create, range(2)))
    assert ids[0] == ids[1]
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(Alert)) == 1
        recipients = set(db.scalars(select(AlertRecipient.user_id)))
        assert user['id'] in recipients and limited_user['id'] not in recipients
        delivery = db.scalar(select(Delivery).where(Delivery.recipient_user_id == user['id']))
        assert service.delivery_allowed(db, delivery)
    member = next(m for m in owner[0].get(f'/api/v1/patients/{pid}/circle').json()['members'] if m['user_id'] == user['id'])
    owner[0].delete(f'/api/v1/patients/{pid}/circle/members/{member["id"]}')
    with Session(db_engine) as db:
        delivery = db.scalar(select(Delivery).where(Delivery.recipient_user_id == user['id']))
        assert delivery.status == 'suppressed' and not service.delivery_allowed(db, delivery)


def test_tampered_expired_and_disabled_sessions_denied(accounts, db_engine):
    client, user = accounts('Session')
    with Session(db_engine) as db, db.begin():
        db.scalar(select(AuthSession).where(AuthSession.user_id == user['id'])).expires_at = utcnow() - timedelta(seconds=1)
    assert client.get('/api/v1/auth/me').status_code == 401
    with TestClient(app) as tampered:
        tampered.cookies.set(SESSION_COOKIE, 'bad.jwt.token', path='/api')
        assert tampered.get('/api/v1/auth/me').status_code == 401
    disabled, disabled_user = accounts('Disabled')
    with Session(db_engine) as db, db.begin():
        db.get(User, disabled_user['id']).disabled_at = utcnow()
    assert disabled.get('/api/v1/auth/me').status_code == 401


def test_preauth_csrf_and_privilege_injection_denied(db_engine):
    with TestClient(app) as client:
        payload = dict(email='new@example.com', password='Strong-example-password-123', display_name='New account')
        client.headers['Origin'] = 'http://localhost:5173'
        assert client.post('/api/v1/auth/register', json=payload).status_code == 401
        token = client.get('/api/v1/auth/csrf').json()['csrf_token']
        assert client.post('/api/v1/auth/register', json=payload).status_code == 403
        client.headers['X-CSRF-Token'] = token
        assert client.post('/api/v1/auth/register', json=payload | {'is_admin': True}).status_code == 422
        assert client.post('/api/v1/auth/register', json=payload, headers={'Origin': 'https://other.example'}).status_code == 403
        assert client.post('/api/v1/auth/register', json=payload).status_code == 201


def test_csrf_token_cannot_cross_sessions(accounts):
    first, _ = accounts('First'); second, _ = accounts('Second')
    assert second.post('/api/v1/auth/logout', headers={'X-CSRF-Token': first.headers['X-CSRF-Token']}).status_code == 403
    assert second.get('/api/v1/auth/me').status_code == 200


def test_alert_creation_participates_in_callers_rollback(owner, db_engine):
    source = uuid4()
    command = RaiseAlertCommand(patient_id=owner[2]['id'], type='vital_threshold', severity='warning',
        source_type='vital', source_id=source, dedupe_key=f'rollback:{source}')
    with Session(db_engine) as db:
        AlertService().raise_alert(db, command, utcnow())
        db.rollback()
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(Alert)) == 0
        assert db.scalar(select(func.count()).select_from(AlertRecipient)) == 0
        assert db.scalar(select(func.count()).select_from(Delivery)) == 0
