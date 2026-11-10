from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.controllers.dependencies import Actor, current_actor
from app.controllers.medicines import patient_access
from app.core.database import get_db
from app.models.identity import utcnow
from app.models.medicines import OcrDraft, PrescriptionVersion
from app.schemas.medicines import OcrReviewInput
from app.services.circle import audit
from app.services import ocr as service

router = APIRouter(prefix='/api/v1/patients/{patient_id}/ocr', tags=['prescription OCR'])


@router.post('', status_code=201)
async def upload(patient_id: UUID, request: Request, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient_access(db, actor, patient_id, True)
    db.rollback()  # Do not hold the patient lock during decoding/OCR.
    if request.headers.get('content-type', '').split(';')[0] not in ('image/png', 'image/jpeg'):
        raise HTTPException(415, 'Upload a JPEG or PNG image')
    length = request.headers.get('content-length')
    if length and length.isdigit() and int(length) > service.MAX_UPLOAD:
        raise HTTPException(413, 'Image must be at most 5 MB')
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > service.MAX_UPLOAD:
            raise HTTPException(413, 'Image must be at most 5 MB')
        content.extend(chunk)
    result = await run_in_threadpool(service.extract, bytes(content))
    db.expire_all()
    patient = patient_access(db, actor, patient_id, True)  # Revocation during OCR is enforced.
    draft = OcrDraft(patient_id=patient.id, uploaded_by=actor.user.id, raw_text=result['text'], reviewed_text=result['text'],
        recognition_status=result['status'], confidence=result['confidence'])
    db.add(draft); db.flush()
    audit(db, actor.user, patient, 'prescription_ocr_created', draft)
    response = service.view(db, draft)
    db.commit()
    return response


@router.get('')
def drafts(patient_id: UUID, offset: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=50),
           actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = patient_access(db, actor, patient_id)
    stmt = select(OcrDraft).where(OcrDraft.patient_id == patient.id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(OcrDraft.created_at.desc(), OcrDraft.id).offset(offset).limit(limit))
    return dict(items=[dict(id=r.id, recognition_status=r.recognition_status, reviewed_at=r.reviewed_at, created_at=r.created_at) for r in rows], total=total, offset=offset, limit=limit)


def find(db, patient, draft_id):
    draft = db.get(OcrDraft, str(draft_id))
    if not draft or draft.patient_id != patient.id:
        raise HTTPException(404, 'OCR draft not found')
    return draft


@router.get('/{draft_id}')
def detail(patient_id: UUID, draft_id: UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    return service.view(db, find(db, patient_access(db, actor, patient_id), draft_id))


@router.put('/{draft_id}')
def review(patient_id: UUID, draft_id: UUID, data: OcrReviewInput,
           actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = patient_access(db, actor, patient_id, True)
    draft = find(db, patient, draft_id)
    if db.scalar(select(PrescriptionVersion.id).where(PrescriptionVersion.ocr_draft_id == draft.id).limit(1)):
        raise HTTPException(409, 'This OCR draft is attached to a confirmed version; upload a new image for a new review')
    if draft.edit_revision != data.expected_revision:
        raise HTTPException(409, 'OCR draft changed; reopen it before reviewing')
    draft.reviewed_text, draft.reviewed_at, draft.reviewed_by = data.reviewed_text, utcnow(), actor.user.id
    draft.edit_revision += 1
    audit(db, actor.user, patient, 'prescription_ocr_reviewed', draft)
    db.flush()
    result = service.view(db, draft)
    db.commit()
    return result
