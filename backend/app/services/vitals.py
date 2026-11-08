"""CC-12 business rules: reading validation context, threshold checks, trend rule and alerts.

Callers own the transaction: this module flushes but never commits.
"""
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.models import User, Vital, VitalThreshold
from app.schemas.contracts import RaiseAlertCommand
from app.schemas.vitals import LIMITS, DIASTOLIC_LIMITS, UNITS
from app.services.alerts import AlertService
from app.services.circle import audit

MGDL_PER_MMOLL = Decimal('18.016')   # glucose: 180.16 g/mol / 10
FUTURE_TOLERANCE = timedelta(minutes=5)
MAX_BACKDATE = timedelta(days=30)

# Unit used when a patient has no threshold row for a kind.
CANONICAL_UNIT = {'bp': 'mmHg', 'sugar': 'mg/dL', 'weight': 'kg', 'spo2': '%'}

# DOCUMENTED TREND RULE (deterministic, no machine learning):
#   Take the patient's last `min_readings` readings of one kind that all fall within the last
#   `window_days` days up to the newest reading. They show a worsening trend when
#   (1) they move strictly in one direction (no equal or reversing step),
#   (2) the net change from first to last is at least `min_change`, and
#   (3) the direction is the worsening one for that kind: blood pressure (systolic) and sugar
#       rising, SpO2 falling. Weight counts in either direction.
# Fewer than `min_readings` readings in the window means "not enough readings", never a trend.
WORSENING = {'bp': 'up', 'sugar': 'up', 'spo2': 'down', 'weight': None}
DEFAULT_TREND = {'bp': Decimal('10'), 'sugar': Decimal('20'), 'weight': Decimal('2'), 'spo2': Decimal('3')}

# Demo values a user can load into the form. They are NOT medical advice or clinical targets.
DEMO_DEFAULTS = {
    'bp': dict(unit='mmHg', lower=90, upper=140, secondary_lower=60, secondary_upper=90),
    'sugar': dict(unit='mg/dL', lower=70, upper=180),
    'spo2': dict(unit='%', lower=92),
    'weight': dict(unit='kg'),
}
alerts = AlertService()


def convert(value: Decimal, kind: str, source: str, target: str) -> Decimal:
    if source == target:
        return value
    if kind == 'sugar':
        return value * MGDL_PER_MMOLL if (source, target) == ('mmol/L', 'mg/dL') else value / MGDL_PER_MMOLL
    raise ValueError('No conversion for this unit pair')


def rule_for(kind, threshold):
    """Effective trend rule as plain Decimals/ints, in the unit the threshold uses."""
    unit = threshold.unit if threshold else CANONICAL_UNIT[kind]
    stored = (threshold.trend_rule if threshold else None) or {}
    default_change = DEFAULT_TREND[kind]
    if kind == 'sugar' and unit == 'mmol/L':
        default_change = (default_change / MGDL_PER_MMOLL).quantize(Decimal('0.1'))
    return dict(unit=unit, min_readings=int(stored.get('min_readings', 3)),
                window_days=int(stored.get('window_days', 14)),
                min_change=Decimal(str(stored.get('min_change', default_change))))


def breaches(vital, threshold):
    """Which bounds a reading crosses. Empty list = in range or no applicable bound."""
    if not threshold:
        return []
    value = convert(vital.value, vital.kind, vital.unit, threshold.unit)
    found = []
    if threshold.lower is not None and value < threshold.lower:
        found.append('below_lower')
    if threshold.upper is not None and value > threshold.upper:
        found.append('above_upper')
    if vital.kind == 'bp' and vital.secondary_value is not None:
        if threshold.secondary_lower is not None and vital.secondary_value < threshold.secondary_lower:
            found.append('secondary_below_lower')
        if threshold.secondary_upper is not None and vital.secondary_value > threshold.secondary_upper:
            found.append('secondary_above_upper')
    return found


def has_bounds(threshold):
    return bool(threshold) and any(getattr(threshold, f) is not None
                                   for f in ('lower', 'upper', 'secondary_lower', 'secondary_upper'))


def threshold_status(vital, threshold):
    if not has_bounds(threshold):
        return 'no_threshold'
    return 'out_of_range' if breaches(vital, threshold) else 'in_range'


def trend_check(values, kind, rule):
    """Pure function: `values` are primary values oldest->newest, already in rule['unit'].

    Returns {'direction','change','readings'} for a worsening trend, otherwise None."""
    needed = rule['min_readings']
    if len(values) < needed:
        return None
    last = values[-needed:]
    steps = [b - a for a, b in zip(last, last[1:])]
    if all(s > 0 for s in steps):
        direction = 'up'
    elif all(s < 0 for s in steps):
        direction = 'down'
    else:
        return None
    if WORSENING[kind] not in (None, direction):
        return None
    change = abs(last[-1] - last[0])
    if change < rule['min_change']:
        return None
    return dict(direction=direction, change=change, readings=needed)


def window_values(session, patient_id, vital, rule):
    """Primary values of this kind in [observed-window, observed], oldest first, in rule unit."""
    rows = session.scalars(select(Vital).where(
        Vital.patient_id == str(patient_id), Vital.kind == vital.kind,
        Vital.observed_at <= vital.observed_at,
        Vital.observed_at >= vital.observed_at - timedelta(days=rule['window_days']))
        .order_by(Vital.observed_at, Vital.id)).all()
    return [convert(r.value, r.kind, r.unit, rule['unit']) for r in rows]


def is_latest(session, vital):
    later = session.scalar(select(Vital.id).where(
        Vital.patient_id == vital.patient_id, Vital.kind == vital.kind,
        Vital.observed_at > vital.observed_at).limit(1))
    return later is None


def get_threshold(session, patient_id, kind):
    return session.scalar(select(VitalThreshold).where(
        VitalThreshold.patient_id == str(patient_id), VitalThreshold.kind == kind))


def record(session, actor, patient, data, now):
    """Validate time rules, store one reading, raise at most one alert per alert type.

    Returns (vital, [(alert_type, alert_id)...]). The caller must hold the patient row lock and
    commit. A rejected request raises before anything is written."""
    observed = data.observed_at or now
    if observed > now + FUTURE_TOLERANCE:
        raise HTTPException(422, 'The measurement time cannot be in the future')
    if observed < now - MAX_BACKDATE:
        raise HTTPException(422, 'Readings older than 30 days cannot be added')
    if session.scalar(select(Vital.id).where(Vital.patient_id == patient.id, Vital.kind == data.kind,
                                             Vital.observed_at == observed)):
        raise HTTPException(409, 'A reading of this kind already exists for that measurement time')
    vital = Vital(patient_id=patient.id, recorded_by=actor.id, kind=data.kind, value=data.value,
                  secondary_value=data.secondary_value, unit=data.unit, observed_at=observed)
    session.add(vital)
    session.flush()
    threshold = get_threshold(session, patient.id, data.kind)
    raised = []

    def raise_for(alert_type, severity):
        alert_id = alerts.raise_alert(session, RaiseAlertCommand(
            patient_id=UUID(patient.id), type=alert_type, severity=severity, source_type='vital',
            source_id=UUID(vital.id), dedupe_key=f'{alert_type}:{vital.id}'), now)
        raised.append((alert_type, str(alert_id)))

    if breaches(vital, threshold):
        raise_for('vital_threshold', 'warning')
    # A back-dated reading is not the newest, so a "current trend" is not evaluated for it.
    if is_latest(session, vital):
        rule = rule_for(data.kind, threshold)
        found = trend_check(window_values(session, patient.id, vital, rule), data.kind, rule)
        if found:
            raise_for('vital_trend', 'info')
    audit(session, actor, patient, 'vital.recorded', vital)
    session.flush()
    return vital, raised


def validate_threshold(kind, data):
    """Business validation of a threshold payload. Raises 422 with a plain message."""
    if data.unit not in UNITS[kind]:
        raise HTTPException(422, 'Unit is not valid for this measurement')
    bounds = (data.lower, data.upper, data.secondary_lower, data.secondary_upper)
    if all(b is None for b in bounds) and data.trend is None:
        raise HTTPException(422, 'Set at least one bound or a trend rule')
    if kind != 'bp' and (data.secondary_lower is not None or data.secondary_upper is not None):
        raise HTTPException(422, 'Only blood pressure has diastolic bounds')
    if data.lower is not None and data.upper is not None and data.lower >= data.upper:
        raise HTTPException(422, 'Lower bound must be below the upper bound')
    if (data.secondary_lower is not None and data.secondary_upper is not None
            and data.secondary_lower >= data.secondary_upper):
        raise HTTPException(422, 'Diastolic lower bound must be below the upper bound')
    low, high = LIMITS[(kind, data.unit)]
    for bound in (data.lower, data.upper):
        if bound is not None and not low <= bound <= high:
            raise HTTPException(422, 'A bound is outside the plausible range')
    for bound in (data.secondary_lower, data.secondary_upper):
        if bound is not None and not DIASTOLIC_LIMITS[0] <= bound <= DIASTOLIC_LIMITS[1]:
            raise HTTPException(422, 'A diastolic bound is outside the plausible range')


def save_threshold(session, actor, patient, kind, data):
    validate_threshold(kind, data)
    row = get_threshold(session, patient.id, kind)
    if not row:
        row = VitalThreshold(patient_id=patient.id, kind=kind, unit=data.unit, updated_by=actor.id)
        session.add(row)
    row.unit, row.updated_by = data.unit, actor.id
    row.lower, row.upper = data.lower, data.upper
    row.secondary_lower, row.secondary_upper = data.secondary_lower, data.secondary_upper
    row.trend_rule = None if data.trend is None else dict(
        min_readings=data.trend.min_readings, window_days=data.trend.window_days,
        min_change=str(data.trend.min_change))
    session.flush()
    audit(session, actor, patient, 'vital_threshold.saved', row)
    return row


def delete_threshold(session, actor, patient, kind):
    row = get_threshold(session, patient.id, kind)
    if not row:
        raise HTTPException(404, 'No threshold is set for this measurement')
    audit(session, actor, patient, 'vital_threshold.deleted', row)
    session.delete(row)
    session.flush()


def current_trend(session, patient_id, kind):
    """Trend status for display: based on the newest reading of the kind."""
    newest = session.scalar(select(Vital).where(Vital.patient_id == str(patient_id), Vital.kind == kind)
                            .order_by(Vital.observed_at.desc(), Vital.id.desc()).limit(1))
    rule = rule_for(kind, get_threshold(session, patient_id, kind))
    if not newest:
        return dict(kind=kind, status='no_readings', rule=rule_view(rule))
    values = window_values(session, patient_id, newest, rule)
    if len(values) < rule['min_readings']:
        return dict(kind=kind, status='insufficient_readings', readings_in_window=len(values),
                    rule=rule_view(rule))
    found = trend_check(values, kind, rule)
    return dict(kind=kind, status='worsening' if found else 'no_trend', readings_in_window=len(values),
                rule=rule_view(rule),
                detail=None if not found else dict(direction=found['direction'], change=fmt(found['change'])))


def fmt(number):
    """Always two decimals, so a fresh object and a value re-read from MySQL serialize identically."""
    return None if number is None else f'{Decimal(number):.2f}'


def rule_view(rule):
    return dict(unit=rule['unit'], min_readings=rule['min_readings'], window_days=rule['window_days'],
                min_change=fmt(rule['min_change']))


def vital_view(vital, threshold, names):
    return dict(id=vital.id, kind=vital.kind, unit=vital.unit, value=fmt(vital.value),
                secondary_value=fmt(vital.secondary_value),
                observed_at=vital.observed_at, recorded_by=vital.recorded_by,
                recorded_by_name=names.get(vital.recorded_by, 'Unknown'),
                threshold_status=threshold_status(vital, threshold))


def threshold_view(row):
    return dict(id=row.id, kind=row.kind, unit=row.unit,
                **{f: fmt(getattr(row, f))
                   for f in ('lower', 'upper', 'secondary_lower', 'secondary_upper')},
                trend=None if row.trend_rule is None else row.trend_rule,
                effective_trend=rule_view(rule_for(row.kind, row)), updated_at=row.updated_at)


def names_for(session, vitals):
    ids = {v.recorded_by for v in vitals}
    if not ids:
        return {}
    return {u.id: u.display_name for u in session.scalars(select(User).where(User.id.in_(ids)))}
