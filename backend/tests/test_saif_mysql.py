"""CC-12 vitals and trend alerts: pure rules, schema validation and real-MySQL workflows."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.main import app
from app.models import Alert, AlertRecipient, AuditEvent, Vital
from app.models.identity import utcnow
from app.schemas.vitals import ThresholdInput, VitalInput
from app.services import vitals as service
from tests.test_sandip_mysql import accept, invite


# ---------------------------------------------------------------- pure rules (no database)

def rule(**changes):
    return dict(unit='mmHg', min_readings=3, window_days=14, min_change=Decimal('10')) | changes


def D(*values):
    return [Decimal(str(v)) for v in values]


def test_trend_needs_enough_readings():
    assert service.trend_check(D(120, 135), 'bp', rule()) is None
    assert service.trend_check([], 'bp', rule()) is None


def test_trend_rising_bp_is_worsening_and_reports_change():
    found = service.trend_check(D(118, 126, 134), 'bp', rule())
    assert found == dict(direction='up', change=Decimal('16'), readings=3)


@pytest.mark.parametrize('values', [
    D(120, 130, 125),          # direction reverses
    D(120, 120, 135),          # an equal step is not "strictly" moving
    D(120, 124, 128),          # monotone but net change 8 < 10
    D(134, 126, 118),          # falling bp is not the worsening direction
])
def test_trend_rejects_non_worsening_patterns(values):
    assert service.trend_check(values, 'bp', rule()) is None


def test_trend_boundary_change_equal_to_minimum_counts():
    assert service.trend_check(D(120, 125, 130), 'bp', rule()) is not None  # exactly 10


def test_trend_uses_only_the_last_n_readings():
    assert service.trend_check(D(200, 100, 118, 126, 134), 'bp', rule()) is not None


def test_trend_direction_per_kind():
    spo2 = rule(unit='%', min_change=Decimal('3'))
    assert service.trend_check(D(97, 95, 93), 'spo2', spo2) is not None       # falling is worse
    assert service.trend_check(D(93, 95, 97), 'spo2', spo2) is None           # rising is fine
    weight = rule(unit='kg', min_change=Decimal('2'))
    assert service.trend_check(D(70, 71, 72.5), 'weight', weight) is not None  # gain
    assert service.trend_check(D(72.5, 71, 70), 'weight', weight) is not None  # loss


def test_sugar_unit_conversion_round_trip():
    mg = service.convert(Decimal('5.5'), 'sugar', 'mmol/L', 'mg/dL')
    assert round(mg) == 99
    assert round(service.convert(mg, 'sugar', 'mg/dL', 'mmol/L'), 2) == Decimal('5.50')
    with pytest.raises(ValueError):
        service.convert(Decimal(1), 'weight', 'kg', 'lb')


# ---------------------------------------------------------------- schema validation

def vital(**changes):
    return dict(kind='bp', unit='mmHg', value='120', secondary_value='80') | changes


def test_valid_inputs_for_every_kind():
    VitalInput(**vital())
    VitalInput(kind='sugar', unit='mmol/L', value='5.4')
    VitalInput(kind='sugar', unit='mg/dL', value='98')
    VitalInput(kind='weight', unit='kg', value='64.25')
    VitalInput(kind='spo2', unit='%', value='97')


@pytest.mark.parametrize('changes', [
    {'secondary_value': None},                       # bp pair required
    {'secondary_value': '130'},                      # systolic must exceed diastolic
    {'secondary_value': '120'},                      # equal is not allowed
    {'value': '301'}, {'value': '49'}, {'secondary_value': '19'},
    {'value': '0'}, {'value': '-5'}, {'value': ''}, {'value': None},
    {'value': 'NaN'}, {'value': 'Infinity'}, {'value': '120.123'},
    {'unit': 'mmol/L'}, {'kind': 'pulse'},
    {'observed_at': '2026-11-01T10:00:00'},          # naive time rejected
    {'actor_user_id': str(uuid4())},                 # unknown field rejected
])
def test_invalid_bp_inputs_rejected(changes):
    with pytest.raises(ValidationError):
        VitalInput(**vital(**changes))


@pytest.mark.parametrize('data', [
    dict(kind='spo2', unit='%', value='101'), dict(kind='spo2', unit='%', value='49.99'),
    dict(kind='spo2', unit='mmHg', value='95'), dict(kind='spo2', unit='%', value='95', secondary_value='80'),
    dict(kind='sugar', unit='mmol/L', value='46'), dict(kind='sugar', unit='mg/dL', value='19'),
    dict(kind='weight', unit='lb', value='150'), dict(kind='weight', unit='kg', value='401'),
])
def test_invalid_other_kinds_rejected(data):
    with pytest.raises(ValidationError):
        VitalInput(**data)


def test_boundary_values_are_inclusive():
    VitalInput(kind='spo2', unit='%', value='100')
    VitalInput(kind='spo2', unit='%', value='50')
    VitalInput(**vital(value='300', secondary_value='200'))


@pytest.mark.parametrize('kind,data', [
    ('bp', dict(unit='mmHg')),                                                  # nothing to check
    ('bp', dict(unit='mmHg', lower='140', upper='90')),                         # lower >= upper
    ('bp', dict(unit='mmHg', upper='1000')),                                    # implausible
    ('bp', dict(unit='mmHg', secondary_lower='90', secondary_upper='60')),
    ('spo2', dict(unit='%', secondary_upper='80')),                             # only bp has a pair
    ('sugar', dict(unit='mmHg', upper='180')),                                  # wrong unit
])
def test_invalid_thresholds_rejected(kind, data):
    with pytest.raises(HTTPException) as caught:
        service.validate_threshold(kind, ThresholdInput(**data))
    assert caught.value.status_code == 422


# ---------------------------------------------------------------- MySQL workflows

mysql = pytest.mark.mysql


def api(patient):
    return f'/api/v1/patients/{patient["id"]}'


def log(client, patient, kind='bp', value='120', secondary='80', hours_ago=0.0, unit=None, **extra):
    body = dict(kind=kind, unit=unit or {'bp': 'mmHg', 'sugar': 'mg/dL', 'weight': 'kg', 'spo2': '%'}[kind],
                value=value, observed_at=(utcnow() - timedelta(hours=hours_ago)).isoformat())
    if kind == 'bp':
        body['secondary_value'] = secondary
    return client.post(f'{api(patient)}/vitals', json=body | extra)


def threshold(client, patient, kind, **body):
    return client.put(f'{api(patient)}/vital-thresholds/{kind}', json=body)


def alert_count(db_engine, patient_id, alert_type=None):
    with Session(db_engine) as db:
        query = select(func.count()).select_from(Alert).where(Alert.patient_id == patient_id)
        if alert_type:
            query = query.where(Alert.type == alert_type)
        return db.scalar(query)


def reading_count(db_engine, patient_id):
    with Session(db_engine) as db:
        return db.scalar(select(func.count()).select_from(Vital).where(Vital.patient_id == patient_id))


@mysql
def test_log_and_list_every_kind_with_filter_order_and_paging(owner):
    client, user, patient = owner
    assert log(client, patient, 'bp', '121', '79', hours_ago=3).status_code == 201
    assert log(client, patient, 'sugar', '5.4', unit='mmol/L', hours_ago=2).status_code == 201
    assert log(client, patient, 'weight', '64.25', hours_ago=1).status_code == 201
    created = log(client, patient, 'spo2', '97')
    assert created.status_code == 201
    body = created.json()
    assert body['value'] == '97.00' and body['recorded_by_name'] == 'Patient'
    assert body['threshold_status'] == 'no_threshold' and body['alerts_raised'] == []
    listing = client.get(f'{api(patient)}/vitals').json()
    assert listing['total'] == 4 and [i['kind'] for i in listing['items']] == ['spo2', 'weight', 'sugar', 'bp']
    assert listing['items'][-1]['secondary_value'] == '79.00'
    assert client.get(f'{api(patient)}/vitals?kind=bp').json()['total'] == 1
    assert len(client.get(f'{api(patient)}/vitals?limit=2&offset=1').json()['items']) == 2
    assert client.get(f'{api(patient)}/vitals?limit=101').status_code == 422
    assert client.get(f'{api(patient)}/vitals?kind=pulse').status_code == 422


@mysql
def test_invalid_readings_are_rejected_and_nothing_is_stored(owner, db_engine):
    client, _, patient = owner
    bad = [dict(kind='bp', unit='mmHg', value='120'),                           # missing diastolic
           dict(kind='bp', unit='mmHg', value='0', secondary_value='0'),        # zero is not a reading
           dict(kind='spo2', unit='%', value=''), dict(kind='spo2', unit='%'),  # empty / missing
           dict(kind='spo2', unit='%', value='101')]
    for body in bad:
        assert client.post(f'{api(patient)}/vitals', json=body).status_code == 422, body
    assert reading_count(db_engine, patient['id']) == 0


@mysql
def test_time_rules_future_old_and_duplicate(owner, db_engine):
    client, _, patient = owner
    assert log(client, patient, 'weight', '70', hours_ago=-1).status_code == 422          # future
    assert log(client, patient, 'weight', '70', hours_ago=24 * 31).status_code == 422     # > 30 days
    stamp = (utcnow() - timedelta(hours=1)).isoformat()
    first = client.post(f'{api(patient)}/vitals', json=dict(kind='weight', unit='kg', value='70', observed_at=stamp))
    again = client.post(f'{api(patient)}/vitals', json=dict(kind='weight', unit='kg', value='70', observed_at=stamp))
    assert (first.status_code, again.status_code) == (201, 409)
    assert reading_count(db_engine, patient['id']) == 1
    # Different kind at the same instant is a different measurement.
    assert client.post(f'{api(patient)}/vitals', json=dict(kind='spo2', unit='%', value='96', observed_at=stamp)).status_code == 201


@mysql
def test_threshold_breach_raises_exactly_one_alert_for_the_reading(owner, db_engine):
    client, user, patient = owner
    saved = threshold(client, patient, 'bp', unit='mmHg', lower='90', upper='140', secondary_lower='60', secondary_upper='90')
    assert saved.status_code == 200 and saved.json()['upper'] == '140.00'
    calm = log(client, patient, 'bp', '130', '85', hours_ago=2).json()
    assert calm['threshold_status'] == 'in_range' and calm['alerts_raised'] == []
    assert alert_count(db_engine, patient['id']) == 0
    high = log(client, patient, 'bp', '150', '85', hours_ago=1)
    assert high.status_code == 201 and high.json()['threshold_status'] == 'out_of_range'
    raised = high.json()['alerts_raised']
    assert [a['type'] for a in raised] == ['vital_threshold']
    assert alert_count(db_engine, patient['id'], 'vital_threshold') == 1
    with Session(db_engine) as db:
        alert = db.scalar(select(Alert).where(Alert.patient_id == patient['id']))
        assert alert.source_type == 'vital' and alert.source_id == high.json()['id']
        assert alert.dedupe_key == f'vital_threshold:{high.json()["id"]}' and alert.severity == 'warning'
        assert db.scalar(select(func.count()).select_from(AlertRecipient).where(AlertRecipient.alert_id == alert.id)) == 1
    # Diastolic-only breach is also caught, still one alert for that reading.
    assert log(client, patient, 'bp', '130', '95', hours_ago=0.5).json()['alerts_raised'][0]['type'] == 'vital_threshold'
    assert alert_count(db_engine, patient['id'], 'vital_threshold') == 2


@mysql
@pytest.mark.parametrize('value,expected', [('92', 'in_range'), ('91.99', 'out_of_range')])
def test_threshold_boundary_is_inclusive(owner, value, expected):
    client, _, patient = owner
    threshold(client, patient, 'spo2', unit='%', lower='92')
    assert log(client, patient, 'spo2', value).json()['threshold_status'] == expected


@mysql
@pytest.mark.parametrize('systolic,diastolic,expected', [
    ('140', '90', 'in_range'),         # exactly on both upper bounds
    ('140.01', '90', 'out_of_range'),  # just above systolic upper
    ('140', '90.01', 'out_of_range'),  # just above diastolic upper
    ('90', '60', 'in_range'),          # exactly on both lower bounds
    ('89.99', '60', 'out_of_range'),
    ('90', '59.99', 'out_of_range'),
])
def test_blood_pressure_bounds_are_inclusive_on_both_sides(owner, systolic, diastolic, expected):
    client, _, patient = owner
    threshold(client, patient, 'bp', unit='mmHg', lower='90', upper='140', secondary_lower='60', secondary_upper='90')
    assert log(client, patient, 'bp', systolic, diastolic).json()['threshold_status'] == expected


@mysql
def test_sugar_readings_in_other_unit_are_converted_before_comparison(owner, db_engine):
    client, _, patient = owner
    threshold(client, patient, 'sugar', unit='mg/dL', lower='70', upper='180')
    assert log(client, patient, 'sugar', '12', unit='mmol/L', hours_ago=2).json()['threshold_status'] == 'out_of_range'  # ~216 mg/dL
    assert log(client, patient, 'sugar', '5.5', unit='mmol/L', hours_ago=1).json()['threshold_status'] == 'in_range'     # ~99 mg/dL
    assert alert_count(db_engine, patient['id'], 'vital_threshold') == 1


@mysql
def test_trend_alert_after_three_worsening_readings_only(owner, db_engine):
    client, _, patient = owner
    first = log(client, patient, 'bp', '120', '80', hours_ago=48).json()
    second = log(client, patient, 'bp', '128', '82', hours_ago=24).json()
    assert first['alerts_raised'] == [] and second['alerts_raised'] == []     # not enough readings yet
    third = log(client, patient, 'bp', '136', '84', hours_ago=0).json()
    assert [a['type'] for a in third['alerts_raised']] == ['vital_trend']
    assert alert_count(db_engine, patient['id'], 'vital_trend') == 1
    with Session(db_engine) as db:
        alert = db.scalar(select(Alert).where(Alert.type == 'vital_trend'))
        assert alert.severity == 'info' and alert.source_id == third['id']
    trend = {t['kind']: t for t in client.get(f'{api(patient)}/vitals/trends').json()['items']}
    assert trend['bp']['status'] == 'worsening' and trend['bp']['detail'] == dict(direction='up', change='16.00')
    assert trend['spo2']['status'] == 'no_readings'


@mysql
def test_trend_not_raised_for_small_flat_or_reversing_changes(owner, db_engine):
    client, _, patient = owner
    for hours, systolic in [(72, '120'), (48, '124'), (24, '128')]:             # net change 8 < 10
        log(client, patient, 'bp', systolic, '80', hours_ago=hours)
    assert alert_count(db_engine, patient['id'], 'vital_trend') == 0
    log(client, patient, 'weight', '70', hours_ago=48); log(client, patient, 'weight', '73', hours_ago=24)
    log(client, patient, 'weight', '70', hours_ago=1)                            # reverses
    assert alert_count(db_engine, patient['id'], 'vital_trend') == 0
    status = {t['kind']: t['status'] for t in client.get(f'{api(patient)}/vitals/trends').json()['items']}
    assert status['bp'] == 'no_trend' and status['weight'] == 'no_trend'


@mysql
def test_trend_window_and_custom_rule(owner, db_engine):
    client, _, patient = owner
    # Readings 20 days apart are outside the default 14-day window: insufficient, not a trend.
    for days, systolic in [(40, '110'), (20, '125'), (0, '140')]:
        log(client, patient, 'bp', systolic, '80', hours_ago=days * 24)
    assert alert_count(db_engine, patient['id'], 'vital_trend') == 0
    assert client.get(f'{api(patient)}/vitals/trends').json()['items'][0]['status'] == 'insufficient_readings'
    # A patient-specific wider window turns the same pattern into a trend for the next reading.
    threshold(client, patient, 'bp', unit='mmHg', trend=dict(min_readings=3, window_days=60, min_change='5'))
    result = log(client, patient, 'bp', '150', '80', hours_ago=-0.0)
    assert [a['type'] for a in result.json()['alerts_raised']] == ['vital_trend']


@mysql
def test_backdated_reading_does_not_raise_a_trend_alert(owner, db_engine):
    client, _, patient = owner
    log(client, patient, 'bp', '120', '80', hours_ago=10)
    log(client, patient, 'bp', '130', '80', hours_ago=5)
    log(client, patient, 'bp', '140', '80', hours_ago=1)                          # trend alert (1)
    assert alert_count(db_engine, patient['id'], 'vital_trend') == 1
    late = log(client, patient, 'bp', '100', '60', hours_ago=20)                  # older than newest
    assert late.status_code == 201 and late.json()['alerts_raised'] == []
    assert alert_count(db_engine, patient['id'], 'vital_trend') == 1


@mysql
def test_threshold_crud_validation_and_delete(owner):
    client, _, patient = owner
    assert threshold(client, patient, 'bp', unit='mmHg').status_code == 422
    assert threshold(client, patient, 'bp', unit='mmHg', lower='140', upper='90').status_code == 422
    assert threshold(client, patient, 'pulse', unit='bpm', upper='100').status_code == 422
    assert threshold(client, patient, 'spo2', unit='%', lower='92').status_code == 200
    assert threshold(client, patient, 'spo2', unit='%', lower='94').status_code == 200   # update, still one row
    listing = client.get(f'{api(patient)}/vital-thresholds').json()
    assert [(t['kind'], t['lower']) for t in listing['items']] == [('spo2', '94.00')]
    assert 'not medical advice' in listing['notice'] and 'bp' in listing['demo_defaults']
    assert client.delete(f'{api(patient)}/vital-thresholds/spo2').status_code == 204
    assert client.delete(f'{api(patient)}/vital-thresholds/spo2').status_code == 404
    assert client.get(f'{api(patient)}/vital-thresholds').json()['items'] == []


@mysql
def test_scopes_read_only_unscoped_unrelated_and_revoked_access(owner, accounts, db_engine):
    client, _, patient = owner
    reader, reader_user = accounts('Reader')
    writer, writer_user = accounts('Writer')
    blind, blind_user = accounts('Blind')
    stranger, _ = accounts('Stranger')
    accept(reader, invite(owner, reader_user['email'], ['vitals:read'])[0])
    writer_token, writer_invite = invite(owner, writer_user['email'], ['vitals:write'])
    accept(writer, writer_token)
    accept(blind, invite(owner, blind_user['email'], ['medicines:read'])[0])
    log(client, patient, 'weight', '70', hours_ago=1)
    base = api(patient)
    # Read-only caregiver can read but not write readings or thresholds.
    assert reader.get(f'{base}/vitals').status_code == 200
    assert reader.get(f'{base}/vital-thresholds').status_code == 200
    assert reader.get(f'{base}/vitals/trends').status_code == 200
    assert log(reader, patient, 'weight', '71').status_code == 403
    assert threshold(reader, patient, 'spo2', unit='%', lower='92').status_code == 403
    assert reader.delete(f'{base}/vital-thresholds/spo2').status_code == 403
    # vitals:write implies read and permits recording.
    assert writer.get(f'{base}/vitals').status_code == 200
    assert log(writer, patient, 'weight', '71', hours_ago=0.5).status_code == 201
    # A member with other scopes only, and an unrelated account, get nothing.
    assert blind.get(f'{base}/vitals').status_code == 403
    assert log(blind, patient, 'weight', '72').status_code == 403
    for suffix in ('vitals', 'vital-thresholds', 'vitals/trends'):
        assert stranger.get(f'{base}/{suffix}').status_code == 404
    assert log(stranger, patient, 'weight', '72').status_code == 404
    with TestClient(app) as anonymous:
        assert anonymous.get(f'{base}/vitals').status_code == 401
    # Revocation takes effect on the next request.
    members = client.get(f'{base}/circle').json()['members']
    member = next(m for m in members if m['email'] == writer_user['email'])
    assert client.delete(f'{base}/circle/members/{member["id"]}').status_code == 204
    assert writer.get(f'{base}/vitals').status_code == 404
    assert log(writer, patient, 'weight', '73').status_code == 404
    assert reading_count(db_engine, patient['id']) == 2


@mysql
def test_csrf_and_origin_are_enforced_on_writes(owner):
    client, _, patient = owner
    body = dict(kind='weight', unit='kg', value='70')
    assert client.post(f'{api(patient)}/vitals', json=body, headers={'X-CSRF-Token': 'bad'}).status_code == 403
    assert client.post(f'{api(patient)}/vitals', json=body, headers={'Origin': 'https://evil.example'}).status_code == 403


@mysql
def test_patients_are_isolated_from_each_other(owner, accounts):
    client, _, patient = owner
    other, _ = accounts('Second')
    other_patient = other.post('/api/v1/patients', json=dict(display_name='Second Synthetic', kind='self', consent=True,
                               consent_basis='I consent to this synthetic test profile.')).json()
    mine = log(client, patient, 'weight', '70', hours_ago=1).json()['id']
    theirs = log(other, other_patient, 'weight', '99', hours_ago=1).json()['id']
    mine_ids = [v['id'] for v in client.get(f'{api(patient)}/vitals').json()['items']]
    their_ids = [v['id'] for v in other.get(f'{api(other_patient)}/vitals').json()['items']]
    assert mine_ids == [mine] and their_ids == [theirs]
    threshold(client, patient, 'weight', unit='kg', upper='80')
    assert other.get(f'{api(other_patient)}/vital-thresholds').json()['items'] == []
    assert other.get(f'{api(patient)}/vitals').status_code == 404


@mysql
def test_alert_recipients_respect_vitals_scope(owner, accounts, db_engine):
    client, user, patient = owner
    seer, seer_user = accounts('Seer')
    unaware, unaware_user = accounts('Unaware')
    accept(seer, invite(owner, seer_user['email'], ['vitals:read', 'alerts:read'])[0])
    accept(unaware, invite(owner, unaware_user['email'], ['alerts:read'])[0])         # alerts but no vitals scope
    threshold(client, patient, 'spo2', unit='%', lower='92')
    assert log(client, patient, 'spo2', '88').json()['alerts_raised'][0]['type'] == 'vital_threshold'
    with Session(db_engine) as db:
        recipients = set(db.scalars(select(AlertRecipient.user_id)))
    assert recipients == {user['id'], seer_user['id']}


@mysql
def test_concurrent_identical_submissions_create_one_reading_and_one_alert(owner, db_engine):
    client, _, patient = owner
    threshold(client, patient, 'spo2', unit='%', lower='92')
    stamp = (utcnow() - timedelta(hours=1)).isoformat()
    body = dict(kind='spo2', unit='%', value='85', observed_at=stamp)
    with ThreadPoolExecutor(4) as pool:
        codes = sorted(pool.map(lambda _: client.post(f'{api(patient)}/vitals', json=body).status_code, range(4)))
    assert codes == [201, 409, 409, 409]
    assert reading_count(db_engine, patient['id']) == 1
    assert alert_count(db_engine, patient['id'], 'vital_threshold') == 1


@mysql
def test_failed_alert_rolls_back_the_reading(owner, db_engine, monkeypatch):
    client, _, patient = owner
    threshold(client, patient, 'spo2', unit='%', lower='92')

    def boom(*args, **kwargs):
        raise HTTPException(409, 'simulated alert failure')
    monkeypatch.setattr(service.alerts, 'raise_alert', boom)
    assert log(client, patient, 'spo2', '80').status_code == 409
    assert reading_count(db_engine, patient['id']) == 0


@mysql
def test_audit_records_actions_without_raw_health_values(owner, db_engine):
    client, user, patient = owner
    threshold(client, patient, 'spo2', unit='%', lower='92')
    reading = log(client, patient, 'spo2', '83.17').json()
    with Session(db_engine) as db:
        events = db.scalars(select(AuditEvent).where(AuditEvent.patient_id == patient['id'])).all()
        actions = {e.action: e for e in events}
        assert {'vital.recorded', 'vital_threshold.saved'} <= set(actions)
        assert actions['vital.recorded'].resource_id == reading['id'] and actions['vital.recorded'].actor_user_id == user['id']
        assert '83.17' not in repr([vars(e) for e in events])


@mysql
def test_unit_inconsistency_in_database_is_impossible_via_api(owner):
    client, _, patient = owner
    # Wrong unit for the kind is rejected by the API contract, not silently stored.
    assert client.post(f'{api(patient)}/vitals', json=dict(kind='weight', unit='lb', value='150')).status_code == 422
    assert client.post(f'{api(patient)}/vitals', json=dict(kind='bp', unit='mmHg', value='120', secondary_value='130')).status_code == 422
