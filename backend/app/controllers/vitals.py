"""CC-12 routes: vitals logging, per-patient thresholds and trend status (Saif)."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.controllers.dependencies import Actor, current_actor
from app.core.database import get_db
from app.models import Vital, VitalThreshold
from app.models.identity import utcnow
from app.schemas.contracts import Scope
from app.schemas.vitals import Kind, ThresholdInput, VitalInput, UNITS
from app.services.access import permissions
from app.services import vitals as service
from app.services.circle import locked_patient

router = APIRouter(prefix='/api/v1', tags=['vitals'])
KINDS = ['bp', 'sugar', 'weight', 'spo2']


def write_access(db, actor, patient_id):
    # Lock the patient row first, then authorize: a concurrent revocation cannot slip in between.
    patient = locked_patient(db, str(patient_id))
    permissions.require(db, actor.user.id, patient.id, Scope.VITALS_WRITE)
    return patient


@router.get('/patients/{patient_id}/vitals')
def list_vitals(patient_id: UUID, kind: Kind | None = None, offset: int = Query(0, ge=0),
                limit: int = Query(20, ge=1, le=100),
                actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    permissions.require(db, actor.user.id, patient_id, Scope.VITALS_READ)
    query = select(Vital).where(Vital.patient_id == str(patient_id))
    if kind:
        query = query.where(Vital.kind == kind)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Vital.observed_at.desc(), Vital.id).offset(offset).limit(limit)).all()
    thresholds = {t.kind: t for t in db.scalars(select(VitalThreshold).where(VitalThreshold.patient_id == str(patient_id)))}
    names = service.names_for(db, rows)
    return dict(items=[service.vital_view(v, thresholds.get(v.kind), names) for v in rows],
                total=total, offset=offset, limit=limit)


@router.post('/patients/{patient_id}/vitals', status_code=201)
def log_vital(patient_id: UUID, data: VitalInput, actor: Actor = Depends(current_actor),
              db: Session = Depends(get_db)):
    patient = write_access(db, actor, patient_id)
    vital, raised = service.record(db, actor.user, patient, data, utcnow())
    threshold = service.get_threshold(db, patient.id, vital.kind)
    result = service.vital_view(vital, threshold, {actor.user.id: actor.user.display_name})
    result['alerts_raised'] = [dict(type=t, alert_id=a) for t, a in raised]
    db.commit()
    return result


@router.get('/patients/{patient_id}/vitals/trends')
def trends(patient_id: UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    permissions.require(db, actor.user.id, patient_id, Scope.VITALS_READ)
    return dict(items=[service.current_trend(db, patient_id, kind) for kind in KINDS])


@router.get('/patients/{patient_id}/vital-thresholds')
def list_thresholds(patient_id: UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    permissions.require(db, actor.user.id, patient_id, Scope.VITALS_READ)
    rows = db.scalars(select(VitalThreshold).where(VitalThreshold.patient_id == str(patient_id))
                      .order_by(VitalThreshold.kind)).all()
    return dict(items=[service.threshold_view(r) for r in rows], units={k: list(v) for k, v in UNITS.items()},
                demo_defaults=service.DEMO_DEFAULTS,
                notice='Demonstration values for this course project. They are not medical advice; '
                       'ask the patient\'s clinician which limits apply.')


@router.put('/patients/{patient_id}/vital-thresholds/{kind}')
def save_threshold(patient_id: UUID, kind: Kind, data: ThresholdInput,
                   actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = write_access(db, actor, patient_id)
    row = service.save_threshold(db, actor.user, patient, kind, data)
    result = service.threshold_view(row)
    db.commit()
    return result


@router.delete('/patients/{patient_id}/vital-thresholds/{kind}', status_code=204)
def delete_threshold(patient_id: UUID, kind: Kind, actor: Actor = Depends(current_actor),
                     db: Session = Depends(get_db)):
    patient = write_access(db, actor, patient_id)
    service.delete_threshold(db, actor.user, patient, kind)
    db.commit()
