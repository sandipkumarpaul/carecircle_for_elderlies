from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models import Alert, AlertRecipient, Delivery, AuditEvent
from app.models.identity import utcnow, AlertPreference
from app.schemas.contracts import RaiseAlertCommand
from app.services.alerts import AlertService
from tests.test_sandip_mysql import invite, accept

pytestmark = pytest.mark.mysql


def raise_alert(db_engine, patient, severity='warning', age=0):
    now = utcnow() - timedelta(minutes=age)
    source = uuid4()
    with Session(db_engine) as db, db.begin():
        aid = str(AlertService().raise_alert(db, RaiseAlertCommand(patient_id=patient['id'],
            type='vital_threshold', severity=severity, source_type='vital', source_id=source,
            dedupe_key=f'vital:{source}'), now))
        db.get(Alert, aid).created_at = now
    return aid


def test_feed_priority_filters_pagination_and_personal_read(owner, accounts, db_engine):
    c, _, p = owner
    reader, user = accounts('Reader')
    token, _ = invite(owner, user['email'], ['alerts:read', 'vitals:read']); accept(reader, token)
    low = raise_alert(db_engine, p, 'info')
    critical_old = raise_alert(db_engine, p, 'critical', 20)
    critical_new = raise_alert(db_engine, p, 'critical')
    path = f'/api/v1/patients/{p["id"]}/alerts'
    assert [r['id'] for r in c.get(path).json()['items']] == [critical_new, critical_old, low]
    assert c.get(path + '?limit=1&offset=1').json()['items'][0]['id'] == critical_old
    assert c.get(path + '?severity=info').json()['total'] == 1
    assert c.get(path + '?status=resolved').json()['total'] == 0
    assert reader.post(f'{path}/{low}/read').status_code == 200
    assert reader.get(path + '?unread=true').json()['total'] == 2
    assert c.get(path + '?unread=true').json()['total'] == 3
    assert reader.post(f'{path}/{low}/acknowledge').status_code == 403
    assert c.get(path + '?limit=101').status_code == 422
    assert c.get(path + '?severity=invalid').status_code == 422


def test_ack_resolve_idempotency_and_dispatch_cancellation(owner, db_engine):
    c, _, p = owner; aid = raise_alert(db_engine, p)
    path = f'/api/v1/patients/{p["id"]}/alerts/{aid}'
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: c.post(path + '/acknowledge'), range(2)))
    assert all(r.status_code == 200 for r in responses)
    assert responses[0].json()['acknowledged_at'] == responses[1].json()['acknowledged_at']
    with Session(db_engine) as db:
        assert set(db.scalars(select(Delivery.status))) == {'cancelled'}
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == 'alert_acknowledged')) == 1
    resolved = c.post(path + '/resolve').json()
    assert resolved['status'] == 'resolved'
    assert c.post(path + '/resolve').json() == resolved
    assert c.post(path + '/acknowledge').json() == resolved
    with Session(db_engine) as db, db.begin():
        # A future escalation stage must also be stopped by the shared gate.
        recipient = db.scalar(select(AlertRecipient).where(AlertRecipient.alert_id == aid))
        delivery = Delivery(patient_id=p['id'], alert_recipient_id=recipient.id, recipient_user_id=recipient.user_id,
            channel='email', template_key='vital_threshold', dedupe_key='late-stage', due_at=utcnow())
        db.add(delivery); db.flush()
        assert not AlertService().delivery_allowed(db, delivery)
        assert delivery.status == 'cancelled'


def test_alert_recipient_source_scope_csrf_and_revocation(owner, accounts, db_engine):
    c, _, p = owner
    reader, user = accounts('Reader')
    limited, lu = accounts('Limited')
    other, _ = accounts('Other')
    for client, u, scopes in [(reader, user, ['alerts:write', 'vitals:read']), (limited, lu, ['alerts:write'])]:
        token, _ = invite(owner, u['email'], scopes); accept(client, token)
    aid = raise_alert(db_engine, p)
    path = f'/api/v1/patients/{p["id"]}/alerts'
    assert other.get(path).status_code == 404
    assert limited.get(path).json()['total'] == 0
    assert limited.post(f'{path}/{aid}/resolve').status_code == 404
    assert c.post(f'{path}/{aid}/resolve', headers={'X-CSRF-Token':'wrong'}).status_code == 403
    member = next(m for m in c.get(f'/api/v1/patients/{p["id"]}/circle').json()['members'] if m['user_id'] == user['id'])
    c.patch(f'/api/v1/patients/{p["id"]}/circle/members/{member["id"]}', json={'role':'secondary', 'scopes':['alerts:write']})
    assert reader.get(path).json()['total'] == 0
    assert reader.post(f'{path}/{aid}/read').status_code == 404
    c.delete(f'/api/v1/patients/{p["id"]}/circle/members/{member["id"]}')
    assert reader.get(path).status_code == 404


@pytest.mark.parametrize('values', [dict(timezone='No/SuchZone'), dict(timezone='UTC', quiet_start='22:00'),
    dict(timezone='UTC', quiet_start='22:00', quiet_end='22:00'), dict(timezone='UTC', quiet_start='25:00', quiet_end='06:00')])
def test_invalid_quiet_hours(owner, values):
    c, _, p = owner
    assert c.put(f'/api/v1/patients/{p["id"]}/alert-preferences', json=values).status_code == 422


def test_preference_is_personal_and_persists(owner, accounts):
    c, _, p = owner
    reader, user = accounts('Prefs')
    token, _ = invite(owner, user['email'], ['alerts:read']); accept(reader, token)
    path = f'/api/v1/patients/{p["id"]}/alert-preferences'
    data = dict(timezone='Asia/Dhaka', quiet_start='22:00', quiet_end='07:00')
    assert reader.put(path, json=data).json() == data
    assert reader.get(path).json() == data
    assert c.get(path).json()['quiet_start'] is None
    assert reader.put(path, json=dict(timezone='UTC')).json()['quiet_start'] is None


@pytest.mark.parametrize('severity,channel,allowed', [('warning','email',False), ('critical','email',True), ('warning','in_app',True)])
def test_quiet_hours_defer_only_noncritical_email(owner, db_engine, severity, channel, allowed):
    _, user, p = owner; aid = raise_alert(db_engine, p, severity)
    now = datetime(2026, 11, 9, 18, 0, tzinfo=timezone.utc)  # midnight Dhaka
    with Session(db_engine) as db, db.begin():
        db.add(AlertPreference(patient_id=p['id'], user_id=user['id'], timezone='Asia/Dhaka', quiet_start='22:00', quiet_end='07:00'))
        delivery = db.scalar(select(Delivery).join(AlertRecipient, AlertRecipient.id == Delivery.alert_recipient_id).where(AlertRecipient.alert_id == aid))
        delivery.channel = channel; delivery.due_at = now
        assert AlertService().delivery_allowed(db, delivery, now) is allowed
        if not allowed:
            assert delivery.due_at == datetime(2026, 11, 10, 1, 0, tzinfo=timezone.utc)
            assert AlertService().delivery_allowed(db, delivery, delivery.due_at)


def test_direct_resolution_and_cross_patient_id(owner, accounts, db_engine):
    c, _, p = owner; aid = raise_alert(db_engine, p)
    outsider, _ = accounts('OtherPatient')
    response = outsider.post('/api/v1/patients', json=dict(display_name='Other', timezone='UTC', kind='self', consent=True, consent_basis='Synthetic test consent'))
    other = response.json()
    assert outsider.post(f'/api/v1/patients/{other["id"]}/alerts/{aid}/resolve').status_code == 404
    result = c.post(f'/api/v1/patients/{p["id"]}/alerts/{aid}/resolve')
    assert result.status_code == 200 and result.json()['status'] == 'resolved'
    assert result.json()['acknowledged_at'] is None


@pytest.mark.parametrize('now,start,end,expected', [
    (datetime(2026, 3, 8, 6, 30, tzinfo=timezone.utc), '22:00', '02:30', datetime(2026, 3, 8, 7, 30, tzinfo=timezone.utc)),
    (datetime(2026, 11, 1, 6, 10, tzinfo=timezone.utc), '00:00', '01:30', datetime(2026, 11, 1, 6, 30, tzinfo=timezone.utc)),
    (datetime(2026, 11, 9, 17, 0, tzinfo=timezone.utc), '10:00', '14:00', datetime(2026, 11, 9, 19, 0, tzinfo=timezone.utc)),
])
def test_quiet_hours_dst_and_daytime_boundaries(owner, db_engine, now, start, end, expected):
    _, user, p = owner; aid = raise_alert(db_engine, p)
    with Session(db_engine) as db, db.begin():
        db.add(AlertPreference(patient_id=p['id'], user_id=user['id'], timezone='America/New_York', quiet_start=start, quiet_end=end))
        delivery = db.scalar(select(Delivery).join(AlertRecipient, AlertRecipient.id == Delivery.alert_recipient_id).where(AlertRecipient.alert_id == aid))
        delivery.channel = 'email'; delivery.due_at = now
        assert not AlertService().delivery_allowed(db, delivery, now)
        assert delivery.due_at == expected
