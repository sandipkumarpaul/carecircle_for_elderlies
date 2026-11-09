"""CC-06 schedule viewing and explicit rolling-horizon refresh."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.controllers.dependencies import Actor, current_actor
from app.controllers.medicines import patient_access
from app.core.database import get_db
from app.models.identity import utcnow
from app.models.doses import DoseEvent
from app.models.medicines import Medicine, PrescriptionItem, PrescriptionVersion
from app.services.schedules import ScheduleService
from app.services.circle import audit

router = APIRouter(prefix='/api/v1/patients', tags=['dose schedules'])


@router.get('/{patient_id}/doses')
def list_doses(patient_id: UUID, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
               actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = patient_access(db, actor, patient_id)
    now = utcnow()
    conditions = (DoseEvent.patient_id == patient.id, DoseEvent.status == 'pending', DoseEvent.scheduled_at >= now)
    total = db.scalar(select(func.count()).select_from(DoseEvent).where(*conditions))
    rows = db.execute(select(DoseEvent, PrescriptionItem, Medicine)
        .join(PrescriptionItem, PrescriptionItem.id == DoseEvent.prescription_item_id)
        .join(Medicine, Medicine.id == PrescriptionItem.medicine_id).where(*conditions)
        .order_by(DoseEvent.scheduled_at, DoseEvent.id).offset(offset).limit(limit)).all()
    return dict(items=[dict(id=d.id, medicine_name=m.brand_name, strength=m.strength,
        scheduled_at=d.scheduled_at, timezone=i.timezone, quantity=str(d.quantity), unit=d.unit,
        status=d.status, meal_relation=i.meal_relation, instructions=i.instructions) for d, i, m in rows],
        total=total, offset=offset, limit=limit)


@router.post('/{patient_id}/doses/refresh')
def refresh(patient_id: UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = patient_access(db, actor, patient_id, True)
    now = utcnow()
    versions = db.scalars(select(PrescriptionVersion).where(PrescriptionVersion.patient_id == patient.id,
        PrescriptionVersion.status == 'confirmed',
        (PrescriptionVersion.effective_until.is_(None)) | (PrescriptionVersion.effective_until > now))).all()
    for version in versions:
        ScheduleService().extend_version(db, version, now)
    audit(db, actor.user, patient, 'dose_schedule_refreshed', patient)
    db.commit()
    return dict(versions_processed=len(versions), horizon_days=14)
