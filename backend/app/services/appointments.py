"""CC-14 business rules: scheduling, checklist, complete/cancel and post-visit prompt.

Callers own the transaction: this module flushes but never commits.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from app.models.appointments import Appointment
from app.models.identity import User, utcnow
from app.schemas.contracts import RaiseAlertCommand, Scope
from app.services.circle import audit

REMINDER_WINDOW_HOURS = 24   # raise a reminder alert this far before the appointment
POST_VISIT_DELAY_HOURS = 1   # post-visit prescription prompt shown after this delay


def _view(appt, names):
    """Serialise one Appointment for an API response."""
    tz = appt.timezone
    local = appt.scheduled_at.astimezone(ZoneInfo(tz))
    return dict(
        id=appt.id, clinician_label=appt.clinician_label, location=appt.location,
        notes=appt.notes, scheduled_at=appt.scheduled_at, scheduled_local=local.isoformat(),
        timezone=tz, status=appt.status,
        checklist=appt.checklist or {'items': []},
        completed_at=appt.completed_at, cancelled_at=appt.cancelled_at,
        cancelled_reason=appt.cancelled_reason,
        post_visit_prompt_at=appt.post_visit_prompt_at,
        post_visit_dismissed_at=appt.post_visit_dismissed_at,
        created_by=appt.created_by,
        created_by_name=names.get(appt.created_by, 'Unknown'),
        created_at=appt.created_at, updated_at=appt.updated_at,
    )


def names_for(session, appts):
    ids = {a.created_by for a in appts}
    if not ids:
        return {}
    return {u.id: u.display_name for u in session.scalars(select(User).where(User.id.in_(ids)))}


def get_or_404(session, patient_id, appt_id):
    appt = session.scalar(select(Appointment).where(
        Appointment.id == str(appt_id), Appointment.patient_id == str(patient_id)))
    if not appt:
        raise HTTPException(404, 'Appointment not found')
    return appt


def create(session, actor, patient, data, now):
    """Validate and persist a new appointment. Returns the saved row."""
    if data.scheduled_at <= now - timedelta(hours=1):
        raise HTTPException(422, 'Appointment time is in the past')
    checklist = {'items': [{'text': i.text, 'done': i.done} for i in data.checklist]}
    appt = Appointment(
        patient_id=patient.id, created_by=actor.id,
        clinician_label=data.clinician_label, location=data.location,
        notes=data.notes, scheduled_at=data.scheduled_at,
        timezone=data.timezone, checklist=checklist, status='scheduled',
    )
    session.add(appt)
    session.flush()
    audit(session, actor, patient, 'appointment.created', appt)
    session.flush()
    return appt


def update(session, actor, patient, appt, data):
    """Apply partial edits to a scheduled appointment."""
    if appt.status != 'scheduled':
        raise HTTPException(409, 'Only scheduled appointments can be edited')
    if data.clinician_label is not None:
        appt.clinician_label = data.clinician_label
    if data.location is not None:
        appt.location = data.location
    if data.notes is not None:
        appt.notes = data.notes
    if data.scheduled_at is not None:
        appt.scheduled_at = data.scheduled_at
    if data.timezone is not None:
        appt.timezone = data.timezone
    if data.checklist is not None:
        appt.checklist = {'items': [{'text': i.text, 'done': i.done} for i in data.checklist]}
    session.flush()
    audit(session, actor, patient, 'appointment.updated', appt)
    session.flush()
    return appt


def update_checklist_item(session, actor, patient, appt, item_index, done):
    """Toggle one checklist item without replacing the whole checklist."""
    if appt.status != 'scheduled':
        raise HTTPException(409, 'Checklist edits are only allowed on scheduled appointments')
    items = (appt.checklist or {'items': []})['items']
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(404, 'Checklist item not found')
    items[item_index]['done'] = done
    appt.checklist = {'items': items}
    session.flush()
    audit(session, actor, patient, 'appointment.checklist_updated', appt)
    session.flush()
    return appt


def complete(session, actor, patient, appt, data, now):
    """Mark an appointment as completed and optionally schedule the post-visit prompt."""
    if appt.status != 'scheduled':
        raise HTTPException(409, 'Only scheduled appointments can be completed')
    appt.status = 'completed'
    appt.completed_at = now
    if data.post_visit_prompt:
        appt.post_visit_prompt_at = now + timedelta(hours=POST_VISIT_DELAY_HOURS)
    session.flush()
    audit(session, actor, patient, 'appointment.completed', appt)
    session.flush()
    return appt


def cancel(session, actor, patient, appt, data, now):
    """Cancel a scheduled appointment. Cancelled appointments do not send reminders."""
    if appt.status != 'scheduled':
        raise HTTPException(409, 'Only scheduled appointments can be cancelled')
    appt.status = 'cancelled'
    appt.cancelled_at = now
    appt.cancelled_reason = data.reason
    session.flush()
    audit(session, actor, patient, 'appointment.cancelled', appt)
    session.flush()
    return appt


def dismiss_post_visit_prompt(session, actor, patient, appt, now):
    """Patient dismisses the post-visit prescription upload prompt."""
    if appt.status != 'completed':
        raise HTTPException(409, 'Post-visit prompt only exists on completed appointments')
    if not appt.post_visit_prompt_at:
        raise HTTPException(404, 'No post-visit prompt for this appointment')
    if appt.post_visit_dismissed_at:
        raise HTTPException(409, 'Post-visit prompt already dismissed')
    appt.post_visit_dismissed_at = now
    session.flush()
    audit(session, actor, patient, 'appointment.prompt_dismissed', appt)
    session.flush()
    return appt


def raise_reminder(session, appt, patient, alerts, now):
    """Raise a task_due alert as a reminder. Called by the controller when due."""
    from app.models.identity import Alert
    from uuid import UUID
    dedupe = f'appointment_reminder:{appt.id}'
    existing = session.scalar(select(Alert).where(
        Alert.patient_id == patient.id, Alert.dedupe_key == dedupe))
    if existing:
        return None
    cmd = RaiseAlertCommand(
        patient_id=UUID(patient.id), type='task_due', severity='info',
        source_type='task', source_id=UUID(appt.id), dedupe_key=dedupe)
    return alerts.raise_alert(session, cmd, now)
