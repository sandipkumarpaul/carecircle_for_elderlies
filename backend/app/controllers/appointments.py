"""CC-14 routes: appointment scheduling, checklist, complete/cancel and post-visit prompt (Saif)."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.controllers.dependencies import Actor, current_actor
from app.core.database import get_db
from app.models.appointments import Appointment
from app.models.identity import utcnow
from app.schemas.appointments import AppointmentCreate, AppointmentUpdate, CancelInput, CompleteInput
from app.schemas.contracts import Scope
from app.services.access import permissions
from app.services import appointments as service
from app.services.alerts import AlertService
from app.services.circle import locked_patient

router = APIRouter(prefix='/api/v1', tags=['appointments'])
alerts = AlertService()


def write_access(db, actor, patient_id):
    patient = locked_patient(db, str(patient_id))
    permissions.require(db, actor.user.id, patient.id, Scope.APPOINTMENTS_WRITE)
    return patient


@router.get('/patients/{patient_id}/appointments')
def list_appointments(patient_id: UUID, status: str | None = None,
                      offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                      actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    permissions.require(db, actor.user.id, patient_id, Scope.APPOINTMENTS_READ)
    query = select(Appointment).where(Appointment.patient_id == str(patient_id))
    if status:
        if status not in ('scheduled', 'completed', 'cancelled'):
            from fastapi import HTTPException
            raise HTTPException(422, 'Status must be scheduled, completed or cancelled')
        query = query.where(Appointment.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Appointment.scheduled_at.desc()).offset(offset).limit(limit)).all()
    names = service.names_for(db, rows)
    return dict(items=[service._view(a, names) for a in rows], total=total, offset=offset, limit=limit)


@router.post('/patients/{patient_id}/appointments', status_code=201)
def create_appointment(patient_id: UUID, data: AppointmentCreate,
                       actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = write_access(db, actor, patient_id)
    appt = service.create(db, actor.user, patient, data, utcnow())
    names = {actor.user.id: actor.user.display_name}
    result = service._view(appt, names)
    db.commit()
    return result


@router.get('/patients/{patient_id}/appointments/{appt_id}')
def get_appointment(patient_id: UUID, appt_id: UUID,
                    actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    permissions.require(db, actor.user.id, patient_id, Scope.APPOINTMENTS_READ)
    appt = service.get_or_404(db, patient_id, appt_id)
    names = service.names_for(db, [appt])
    return service._view(appt, names)


@router.patch('/patients/{patient_id}/appointments/{appt_id}')
def update_appointment(patient_id: UUID, appt_id: UUID, data: AppointmentUpdate,
                       actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = write_access(db, actor, patient_id)
    appt = service.get_or_404(db, patient_id, appt_id)
    appt = service.update(db, actor.user, patient, appt, data)
    names = service.names_for(db, [appt])
    result = service._view(appt, names)
    db.commit()
    return result


@router.patch('/patients/{patient_id}/appointments/{appt_id}/checklist/{item_index}')
def update_checklist_item(patient_id: UUID, appt_id: UUID, item_index: int,
                          done: bool = Query(...),
                          actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = write_access(db, actor, patient_id)
    appt = service.get_or_404(db, patient_id, appt_id)
    appt = service.update_checklist_item(db, actor.user, patient, appt, item_index, done)
    names = service.names_for(db, [appt])
    result = service._view(appt, names)
    db.commit()
    return result


@router.post('/patients/{patient_id}/appointments/{appt_id}/complete')
def complete_appointment(patient_id: UUID, appt_id: UUID, data: CompleteInput,
                         actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = write_access(db, actor, patient_id)
    appt = service.get_or_404(db, patient_id, appt_id)
    appt = service.complete(db, actor.user, patient, appt, data, utcnow())
    names = service.names_for(db, [appt])
    result = service._view(appt, names)
    db.commit()
    return result


@router.post('/patients/{patient_id}/appointments/{appt_id}/cancel')
def cancel_appointment(patient_id: UUID, appt_id: UUID, data: CancelInput,
                       actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = write_access(db, actor, patient_id)
    appt = service.get_or_404(db, patient_id, appt_id)
    appt = service.cancel(db, actor.user, patient, appt, data, utcnow())
    names = service.names_for(db, [appt])
    result = service._view(appt, names)
    db.commit()
    return result


@router.post('/patients/{patient_id}/appointments/{appt_id}/dismiss-prompt')
def dismiss_post_visit_prompt(patient_id: UUID, appt_id: UUID,
                              actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = write_access(db, actor, patient_id)
    appt = service.get_or_404(db, patient_id, appt_id)
    appt = service.dismiss_post_visit_prompt(db, actor.user, patient, appt, utcnow())
    names = service.names_for(db, [appt])
    result = service._view(appt, names)
    db.commit()
    return result
