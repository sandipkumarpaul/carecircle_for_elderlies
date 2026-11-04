from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.controllers.dependencies import Actor, current_actor
from app.core.database import get_db
from app.core.config import settings
from app.models import Invite, Membership, Patient, User
from app.models.identity import utcnow
from app.schemas.contracts import Scope
from app.schemas.identity import AcceptInput, GrantInput, InviteInput, PatientInput, TokenInput
from app.services import circle
from app.services.access import permissions

router = APIRouter(prefix='/api/v1', tags=['care-circle'])


def patient_view(db, actor, patient):
    _, role, scopes = permissions.context(db, actor.id, patient.id)
    return dict(id=patient.id, display_name=patient.display_name, timezone=patient.timezone,
                role=role, scopes=sorted(scopes), can_manage='circle:manage' in scopes)


def member_view(db, member):
    user = db.get(User, member.user_id)
    return dict(id=member.id, user_id=member.user_id, display_name=user.display_name,
                email=user.email_normalized, role=member.role, scopes=member.scopes,
                accepted_at=member.accepted_at, revoked_at=member.revoked_at)


def invite_view(invite):
    return dict(id=invite.id, email=invite.email_normalized, role=invite.role, scopes=invite.scopes,
                expires_at=invite.expires_at, accepted_at=invite.accepted_at, revoked_at=invite.revoked_at)


@router.get('/patients')
def patients(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
             actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    visible = or_(Patient.user_id == actor.user.id, exists().where(
        Membership.patient_id == Patient.id, Membership.user_id == actor.user.id,
        Membership.accepted_at.is_not(None), Membership.revoked_at.is_(None)))
    total = db.scalar(select(func.count()).select_from(Patient).where(visible))
    rows = db.scalars(select(Patient).where(visible).order_by(Patient.created_at, Patient.id).offset(offset).limit(limit))
    return dict(items=[patient_view(db, actor.user, p) for p in rows], total=total, offset=offset, limit=limit)


@router.post('/patients', status_code=201)
def create_patient(data: PatientInput, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = circle.create_patient(db, actor.user, data)
    result = patient_view(db, actor.user, patient)
    db.commit()
    return result


@router.get('/patients/{patient_id}')
def patient_detail(patient_id: UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient, _, _ = permissions.context(db, actor.user.id, patient_id)
    return patient_view(db, actor.user, patient)


@router.get('/patients/{patient_id}/circle')
def get_circle(patient_id: UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    permissions.require(db, actor.user.id, patient_id, Scope.CIRCLE_MANAGE)
    patient = db.get(Patient, str(patient_id))
    members = db.scalars(select(Membership).where(Membership.patient_id == str(patient_id)).order_by(Membership.created_at, Membership.id))
    invites = db.scalars(select(Invite).where(Invite.patient_id == str(patient_id)).order_by(Invite.created_at.desc(), Invite.id))
    result = dict(patient=patient_view(db, actor.user, patient), members=[member_view(db, m) for m in members],
                  invitations=[invite_view(i) for i in invites])
    circle.audit(db, actor.user, patient, 'circle.viewed', patient)
    db.commit()
    return result


@router.post('/patients/{patient_id}/circle/invites', status_code=201)
def invite(patient_id: UUID, data: InviteInput, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    record, token = circle.create_invite(db, actor.user, patient_id, data)
    result = invite_view(record) | {'invite_url': settings()['origin'] + '/#invite=' + token}
    db.commit()
    return result


@router.delete('/patients/{patient_id}/circle/invites/{invite_id}', status_code=204)
def revoke_invite(patient_id: UUID, invite_id: UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = circle.locked_patient(db, patient_id)
    permissions.require(db, actor.user.id, patient_id, Scope.CIRCLE_MANAGE)
    record = db.get(Invite, str(invite_id))
    if not record or record.patient_id != str(patient_id):
        raise HTTPException(404, 'Invitation not found')
    if record.role == 'primary' and patient.user_id != actor.user.id:
        raise HTTPException(403, 'Only the patient can revoke a primary invitation')
    if record.accepted_at:
        raise HTTPException(409, 'This invitation was accepted; revoke the member instead')
    record.revoked_at = utcnow()
    circle.audit(db, actor.user, patient, 'circle.invitation_revoked', record)
    db.commit()


@router.post('/circle/invites/preview')
def preview(data: TokenInput, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    record, patient = circle.valid_invite(db, actor.user, data.token)
    return invite_view(record) | {'patient_name': patient.display_name}


@router.post('/circle/invites/accept')
def accept(data: AcceptInput, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    patient = circle.accept_invite(db, actor.user, data.token)
    result = patient_view(db, actor.user, patient)
    db.commit()
    return result


@router.patch('/patients/{patient_id}/circle/members/{member_id}')
def change(patient_id: UUID, member_id: UUID, data: GrantInput,
           actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    member = circle.change_member(db, actor.user, patient_id, member_id, data)
    result = member_view(db, member)
    db.commit()
    return result


@router.delete('/patients/{patient_id}/circle/members/{member_id}', status_code=204)
def revoke(patient_id: UUID, member_id: UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    circle.change_member(db, actor.user, patient_id, member_id)
    db.commit()
