"""CC-18 recipient feed and lifecycle. Caller locks patient and commits."""
from fastapi import HTTPException
from sqlalchemy import select, func, case, update
from app.models import Alert, AlertRecipient, Delivery
from app.models.identity import AlertPreference
from app.services.access import permissions
from app.services.alerts import SOURCE_SCOPE
from app.services.circle import audit
from app.schemas.contracts import Scope


def sources(db, user, patient):
    permissions.require(db, user.id, patient.id, Scope.ALERTS_READ)
    _, _, scopes = permissions.context(db, user.id, patient.id)
    return [source for source, scope in SOURCE_SCOPE.items() if scope.value in scopes]


def view(alert, recipient):
    return dict(id=alert.id, type=alert.type, severity=alert.severity, status=alert.status,
        source_type=alert.source_type, source_id=alert.source_id, created_at=alert.created_at,
        read_at=recipient.read_at, acknowledged_at=alert.acknowledged_at, resolved_at=alert.resolved_at)


def feed(db, user, patient, status, severity, unread, offset, limit):
    conditions = [Alert.patient_id == patient.id, AlertRecipient.user_id == user.id,
                  Alert.source_type.in_(sources(db, user, patient))]
    if status:
        conditions.append(Alert.status == status)
    if severity:
        conditions.append(Alert.severity == severity)
    if unread:
        conditions.append(AlertRecipient.read_at.is_(None))
    base = select(Alert, AlertRecipient).join(AlertRecipient, AlertRecipient.alert_id == Alert.id).where(*conditions)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.execute(base.order_by(case((Alert.severity == 'critical', 0), (Alert.severity == 'warning', 1), else_=2),
        Alert.created_at.desc(), Alert.id).offset(offset).limit(limit)).all()
    return dict(items=[view(a, r) for a, r in rows], total=total, offset=offset, limit=limit)


def change(db, user, patient, alert_id, action, now):
    permitted = sources(db, user, patient)
    row = db.execute(select(Alert, AlertRecipient).join(AlertRecipient, AlertRecipient.alert_id == Alert.id)
        .where(Alert.id == str(alert_id), Alert.patient_id == patient.id,
               AlertRecipient.user_id == user.id, Alert.source_type.in_(permitted)).with_for_update()).first()
    if not row:
        raise HTTPException(404, 'Alert not found')
    alert, recipient = row
    if action != 'read':
        permissions.require(db, user.id, patient.id, Scope.ALERTS_WRITE)
    if action == 'read':
        if recipient.read_at is None:
            recipient.read_at = now
            audit(db, user, patient, 'alert_read', alert)
    elif action == 'acknowledge':
        if alert.status == 'open':
            alert.status = 'acknowledged'
            alert.acknowledged_by, alert.acknowledged_at = user.id, now
            audit(db, user, patient, 'alert_acknowledged', alert)
    elif action == 'resolve':
        if alert.status != 'resolved':
            alert.status = 'resolved'
            alert.resolved_by, alert.resolved_at = user.id, now
            audit(db, user, patient, 'alert_resolved', alert)
    if action != 'read':
        recipient.read_at = recipient.read_at or now
        recipients = select(AlertRecipient.id).where(AlertRecipient.alert_id == alert.id)
        db.execute(update(Delivery).where(Delivery.alert_recipient_id.in_(recipients),
            Delivery.status == 'pending').values(status='cancelled'))
    db.flush()
    return view(alert, recipient)


def preference(db, user, patient):
    permissions.require(db, user.id, patient.id, Scope.ALERTS_READ)
    row = db.scalar(select(AlertPreference).where(AlertPreference.patient_id == patient.id, AlertPreference.user_id == user.id))
    return row


def preference_view(row, patient):
    return dict(timezone=row.timezone if row else patient.timezone,
                quiet_start=row.quiet_start if row else None, quiet_end=row.quiet_end if row else None)


def save_preference(db, user, patient, data):
    row = preference(db, user, patient)
    if row is None:
        row = AlertPreference(patient_id=patient.id, user_id=user.id)
        db.add(row)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.flush()
    audit(db, user, patient, 'alert_preferences_updated', row)
    return preference_view(row, patient)
