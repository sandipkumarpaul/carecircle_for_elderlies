from uuid import UUID
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Alert, AlertRecipient, Delivery, Membership
from app.schemas.contracts import Scope
from app.services.access import permissions
from app.services.circle import locked_patient
from app.models.identity import AlertPreference, utcnow
from app.services.schedules import local_time_to_utc

SOURCE_SCOPE = {'dose_event': Scope.ADHERENCE_READ, 'vital': Scope.VITALS_READ,
                'stock': Scope.MEDICINES_READ, 'checkin': Scope.ADHERENCE_READ,
                'prescription_version': Scope.MEDICINES_READ, 'symptom': Scope.SYMPTOMS_READ,
                'risk_prediction': Scope.ADHERENCE_READ, 'task': Scope.TASKS_READ}
TYPE_SOURCE = {'missed_dose': 'dose_event', 'vital_threshold': 'vital', 'vital_trend': 'vital',
               'low_stock': 'stock', 'stock_reconciliation': 'stock', 'checkin_missed': 'checkin',
               'prescription_changed': 'prescription_version', 'possible_side_effect': 'symptom',
               'adherence_risk': 'risk_prediction', 'task_due': 'task'}


class AlertService:
    """Internal trusted service. Caller must validate source ownership before invoking."""
    def raise_alert(self, session, command, now):
        if command.type == 'sos':
            raise HTTPException(409, 'SOS consent and emergency delivery belong to CC-16 and are not implemented yet')
        if TYPE_SOURCE.get(command.type) != command.source_type:
            raise HTTPException(422, 'Alert type and source do not match')
        patient = locked_patient(session, command.patient_id)
        existing = session.scalar(select(Alert).where(Alert.patient_id == patient.id, Alert.dedupe_key == command.dedupe_key))
        if existing:
            if (existing.type, existing.source_id, existing.source_type, existing.severity) != (
                    command.type, str(command.source_id), command.source_type, command.severity):
                raise HTTPException(409, 'Alert key already belongs to another payload')
            return UUID(existing.id)
        alert = Alert(patient_id=patient.id, type=command.type, severity=command.severity,
                      source_type=command.source_type, source_id=str(command.source_id), dedupe_key=command.dedupe_key)
        session.add(alert)
        session.flush()
        users = set(session.scalars(select(Membership.user_id).where(Membership.patient_id == patient.id,
                    Membership.revoked_at.is_(None), Membership.accepted_at.is_not(None))))
        if patient.user_id:
            users.add(patient.user_id)
        for user_id in users:
            try:
                permissions.require(session, user_id, patient.id, Scope.ALERTS_READ)
                permissions.require(session, user_id, patient.id, SOURCE_SCOPE[command.source_type])
            except HTTPException:
                continue
            recipient = AlertRecipient(alert_id=alert.id, user_id=user_id)
            session.add(recipient)
            session.flush()
            session.add(Delivery(patient_id=patient.id, alert_recipient_id=recipient.id, recipient_user_id=user_id,
                                 template_key=command.type, dedupe_key=f'{alert.id}:{user_id}:in_app', due_at=now))
        session.flush()
        return UUID(alert.id)

    def delivery_allowed(self, session, delivery, now=None):
        """Pre-dispatch gate; caller holds patient lock and commits deferrals.

        Future dispatchers must recheck this gate immediately before sending.
        This method does not send email or create a worker.
        """
        now = now or utcnow()
        recipient = session.get(AlertRecipient, delivery.alert_recipient_id)
        alert = session.get(Alert, recipient.alert_id) if recipient else None
        if not alert or delivery.status != 'pending':
            return False
        # Refresh shared state so a long-lived dispatcher session cannot reuse stale status.
        session.refresh(alert)
        if alert.status != 'open':
            delivery.status = 'cancelled'
            return False
        try:
            permissions.require(session, delivery.recipient_user_id, delivery.patient_id, Scope.ALERTS_READ)
            permissions.require(session, delivery.recipient_user_id, delivery.patient_id, SOURCE_SCOPE[alert.source_type])
            if delivery.due_at > now:
                return False
            if delivery.channel == 'email' and alert.severity != 'critical':
                pref = session.scalar(select(AlertPreference).where(
                    AlertPreference.patient_id == delivery.patient_id,
                    AlertPreference.user_id == delivery.recipient_user_id))
                if pref and pref.quiet_start is not None:
                    zone = ZoneInfo(pref.timezone)
                    local = now.astimezone(zone)
                    clock = local.strftime('%H:%M')
                    start, end = pref.quiet_start, pref.quiet_end
                    quiet = start <= clock < end if start < end else clock >= start or clock < end
                    if quiet:
                        day = local.date() + timedelta(days=int(start > end and clock >= start))
                        delivery.due_at = local_time_to_utc(day, time.fromisoformat(end), zone)
                        # In the second occurrence of a DST overlap, the first
                        # end-time occurrence can already be past. Use the second.
                        if delivery.due_at <= now:
                            delivery.due_at = datetime.combine(day, time.fromisoformat(end)).replace(
                                tzinfo=zone, fold=1).astimezone(timezone.utc)
                        return False
            return True
        except (HTTPException, KeyError):
            return False
