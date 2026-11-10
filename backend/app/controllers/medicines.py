from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.controllers.dependencies import Actor, current_actor
from app.core.database import get_db
from app.models import AuditEvent
from app.models.identity import utcnow
from app.models.medicines import Medicine, InteractionRule, PrescriptionVersion, PrescriptionItem
from app.schemas.contracts import Scope
from app.schemas.medicines import ImportInput, RuleInput, AllergyInput, CheckInput, ConfirmInput, StopInput
from app.services.access import permissions
from app.services.circle import locked_patient, audit
from app.services import medicines as service

router = APIRouter(prefix='/api/v1', tags=['medicines'])


def admin(actor):
    if not actor.user.is_admin:
        raise HTTPException(403, 'Reference-data administrator required')


@router.get('/medicines')
def search(q: str = Query('', max_length=160), generic: str = Query('', max_length=160), strength: str = Query('', max_length=60),
           form: str = Query('', max_length=30), offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
           actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    return service.search(db, q, strength, form, offset, limit, generic)


@router.post('/medicines/import')
def import_medicines(data: ImportInput, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    admin(actor)
    result = service.import_csv(db, data.csv_text, actor.user)
    db.commit()
    return result


@router.get('/medicines/interaction-rules')
def rules(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    return {'items': [dict(id=r.id, medicine_a_id=r.medicine_a_id, medicine_b_id=r.medicine_b_id,
        severity=r.severity, explanation=r.explanation, source=r.source)
        for r in db.scalars(select(InteractionRule).order_by(InteractionRule.created_at, InteractionRule.id))]}


@router.post('/medicines/interaction-rules')
def save_rule(data: RuleInput, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    admin(actor)
    revision = service.reference_lock(db)
    a, b = sorted([str(data.medicine_a_id), str(data.medicine_b_id)])
    if not db.get(Medicine, a) or not db.get(Medicine, b):
        raise HTTPException(422, 'Both medicines must exist')
    row = db.scalar(select(InteractionRule).where(InteractionRule.medicine_a_id == a, InteractionRule.medicine_b_id == b))
    if not row:
        row = InteractionRule(medicine_a_id=a, medicine_b_id=b); db.add(row)
    row.severity, row.explanation, row.source = data.severity, data.explanation, data.source
    revision.revision += 1
    db.flush()
    db.add(AuditEvent(actor_user_id=actor.user.id, action='interaction_rule_saved', resource_type='interaction_rules', resource_id=row.id))
    db.commit()
    return {'id': row.id}


def patient_access(db, actor, patient_id, write=False):
    # Lock first, then authorize, so a concurrent membership change cannot race a write.
    patient = locked_patient(db, str(patient_id))
    permissions.require(db, actor.user.id, patient.id, Scope.MEDICINES_WRITE if write else Scope.MEDICINES_READ)
    return patient


@router.get('/patients/{patient_id}/allergies')
def allergies(patient_id: UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = patient_access(db, actor, patient_id)
    return {'generic_names': patient.allergies, 'source': 'Patient/caregiver reported'}


@router.put('/patients/{patient_id}/allergies')
def save_allergies(patient_id: UUID, data: AllergyInput, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = patient_access(db, actor, patient_id, True)
    patient.allergies = data.generic_names
    audit(db, actor.user, patient, 'allergies_updated', patient)
    db.commit()
    return {'generic_names': patient.allergies}


@router.get('/patients/{patient_id}/prescriptions')
def prescriptions(patient_id: UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = patient_access(db, actor, patient_id)
    result = []
    for item, med, version in service.active_items(db, patient.id, utcnow()):
        result.append(dict(id=item.id, medicine=service.medicine_view(med), version_id=version.id, prescription_id=version.prescription_id,
            schedule_status=version.schedule_status, **{k: getattr(item, k) for k in (
            'quantity_per_dose', 'unit', 'start_date', 'end_date', 'schedule_kind', 'times_local', 'timezone', 'meal_relation', 'instructions')}))
    for row in result:
        row['quantity_per_dose'] = str(row['quantity_per_dose'])
    result.sort(key=lambda r: r['id'])
    return {'items': result}


@router.post('/patients/{patient_id}/interaction-check')
def check(patient_id: UUID, data: CheckInput, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    revision = service.reference_lock(db)
    patient = patient_access(db, actor, patient_id, True)
    result = service.check(db, patient, actor.user, data, utcnow(), revision)
    db.commit()
    return result


@router.post('/patients/{patient_id}/prescriptions/confirm')
def confirm(patient_id: UUID, data: ConfirmInput, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    revision = service.reference_lock(db)
    patient = patient_access(db, actor, patient_id, True)
    result = service.confirm(db, patient, actor.user, data, utcnow(), revision)
    db.commit()
    return result


@router.get('/patients/{patient_id}/prescription-history')
def history(patient_id: UUID, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
            actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = patient_access(db, actor, patient_id)
    stmt = select(PrescriptionVersion).where(PrescriptionVersion.patient_id == patient.id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    versions = db.scalars(stmt.order_by(PrescriptionVersion.created_at.desc(), PrescriptionVersion.id).offset(offset).limit(limit)).all()
    result = []
    for version in versions:
        items = db.execute(select(PrescriptionItem, Medicine).join(Medicine, Medicine.id == PrescriptionItem.medicine_id)
            .where(PrescriptionItem.prescription_version_id == version.id).order_by(PrescriptionItem.id)).all()
        result.append(dict(id=version.id, prescription_id=version.prescription_id, version_number=version.version_number,
            status=version.status, current=version.status == 'confirmed' and version.effective_until is None,
            effective_from=version.effective_from, effective_until=version.effective_until, change_reason=version.change_reason,
            previous_version_id=version.previous_version_id, ocr_draft_id=version.ocr_draft_id,
            items=[dict(medicine=service.medicine_view(m), **{k:getattr(i,k) for k in (
                'medicine_id','unit','start_date','end_date','schedule_kind','times_local','timezone','meal_relation','instructions')},
                quantity_per_dose=str(i.quantity_per_dose)) for i,m in items]))
    return dict(items=result, total=total, offset=offset, limit=limit)


@router.post('/patients/{patient_id}/prescriptions/{prescription_id}/stop')
def stop(patient_id: UUID, prescription_id: UUID, data: StopInput,
         actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    service.reference_lock(db)
    patient = patient_access(db, actor, patient_id, True)
    result = service.stop(db, patient, actor.user, prescription_id, data, utcnow())
    db.commit()
    return result
