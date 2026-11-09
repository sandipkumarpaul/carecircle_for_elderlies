from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.controllers.dependencies import Actor, current_actor
from app.core.database import get_db
from app.models.identity import utcnow
from app.schemas.alerts import QuietHoursInput
from app.services.circle import locked_patient
from app.services import alert_center as service

router = APIRouter(prefix='/api/v1/patients/{patient_id}', tags=['alert center'])


@router.get('/alerts')
def feed(patient_id: UUID, status: Literal['open', 'acknowledged', 'resolved'] | None = None,
         severity: Literal['info', 'warning', 'critical'] | None = None, unread: bool = False,
         offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
         actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    return service.feed(db, actor.user, locked_patient(db, patient_id), status, severity, unread, offset, limit)


@router.post('/alerts/{alert_id}/{action}')
def change(patient_id: UUID, alert_id: UUID, action: Literal['read', 'acknowledge', 'resolve'],
           actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    result = service.change(db, actor.user, locked_patient(db, patient_id), alert_id, action, utcnow())
    db.commit()
    return result


@router.get('/alert-preferences')
def preferences(patient_id: UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = locked_patient(db, patient_id)
    return service.preference_view(service.preference(db, actor.user, patient), patient)


@router.put('/alert-preferences')
def save_preferences(patient_id: UUID, data: QuietHoursInput,
                     actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    result = service.save_preference(db, actor.user, locked_patient(db, patient_id), data)
    db.commit()
    return result
