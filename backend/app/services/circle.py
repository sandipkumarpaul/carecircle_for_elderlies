import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select, update

from app.core.security import digest
from app.models import AuditEvent, Delivery, Invite, Membership, Patient, User
from app.models.identity import utcnow
from app.schemas.contracts import Scope
from app.services.access import ALL_SCOPES, expanded, permissions


def audit(session, actor, patient, action, resource):
    session.add(AuditEvent(patient_id=patient.id, actor_user_id=actor.id, action=action,
                           resource_type=resource.__tablename__, resource_id=resource.id))


def locked_patient(session, patient_id):
    patient = session.scalar(select(Patient).where(Patient.id == str(patient_id)).with_for_update()
                             .execution_options(populate_existing=True))
    if not patient:
        raise HTTPException(404, 'Patient not found')
    return patient


def authorize_grant(session, actor, patient, role, scopes):
    permissions.require(session, actor.id, patient.id, Scope.CIRCLE_MANAGE)
    _, actor_role, actor_scopes = permissions.context(session, actor.id, patient.id)
    if role == 'primary' and actor_role != 'patient':
        raise HTTPException(403, 'Only the patient can appoint a primary caregiver')
    if not expanded(scopes).issubset(actor_scopes):
        raise HTTPException(403, 'You cannot grant access you do not have')


def create_patient(session, actor, data):
    # Serialize self-profile creation to enforce one self-profile per user.
    session.scalar(select(User).where(User.id == actor.id).with_for_update())
    if data.kind == 'self' and session.scalar(select(Patient.id).where(Patient.user_id == actor.id)):
        raise HTTPException(409, 'You already have a personal patient profile')
    patient = Patient(user_id=actor.id if data.kind == 'self' else None, display_name=data.display_name,
                      timezone=data.timezone, consent_recorded_at=utcnow(), consent_recorded_by=actor.id,
                      consent_basis=data.consent_basis)
    session.add(patient)
    session.flush()
    if data.kind == 'dependent':
        session.add(Membership(patient_id=patient.id, user_id=actor.id, role='primary',
                               scopes=sorted(ALL_SCOPES), accepted_at=utcnow()))
    audit(session, actor, patient, 'patient.created_with_consent', patient)
    session.flush()
    return patient


def create_invite(session, actor, patient_id, data):
    patient = locked_patient(session, patient_id)
    scopes = [scope.value for scope in data.scopes]
    authorize_grant(session, actor, patient, data.role, scopes)
    email = str(data.email).lower()
    owner = session.get(User, patient.user_id) if patient.user_id else None
    if email == actor.email_normalized or (owner and email == owner.email_normalized):
        raise HTTPException(409, 'The patient and current inviter cannot be invited')
    existing_user = session.scalar(select(User).where(User.email_normalized == email))
    if existing_user and session.scalar(select(Membership.id).where(
            Membership.patient_id == patient.id, Membership.user_id == existing_user.id,
            Membership.revoked_at.is_(None), Membership.accepted_at.is_not(None))):
        raise HTTPException(409, 'This person is already in the care circle')
    now = utcnow()
    if session.scalar(select(Invite.id).where(Invite.patient_id == patient.id,
            Invite.email_normalized == email, Invite.accepted_at.is_(None), Invite.revoked_at.is_(None), Invite.expires_at > now)):
        raise HTTPException(409, 'An active invitation already exists; revoke it before replacing it')
    if data.role == 'primary' and session.scalar(select(Membership.id).where(
            Membership.patient_id == patient.id, Membership.role == 'primary', Membership.revoked_at.is_(None))):
        raise HTTPException(409, 'Revoke the existing primary caregiver before appointing another')
    token = secrets.token_urlsafe(32)
    invite = Invite(patient_id=patient.id, email_normalized=email, token_hash=digest(token), role=data.role,
                    scopes=scopes, invited_by=actor.id, expires_at=now + timedelta(hours=data.expires_in_hours))
    session.add(invite)
    session.flush()
    audit(session, actor, patient, 'circle.invited_with_consent', invite)
    return invite, token


def valid_invite(session, actor, token, lock=False):
    # Find patient, then take the patient lock first to keep a consistent lock order.
    invite = session.scalar(select(Invite).where(Invite.token_hash == digest(token)))
    if not invite or invite.email_normalized != actor.email_normalized:
        raise HTTPException(404, 'Invitation not found for this account')
    patient = locked_patient(session, invite.patient_id) if lock else session.get(Patient, invite.patient_id)
    session.refresh(invite)
    if invite.revoked_at or invite.accepted_at or invite.expires_at <= utcnow():
        raise HTTPException(409, 'This invitation has expired, was revoked, or has already been accepted')
    # Revoked or narrowed inviters cannot leave privileged pending invitations behind.
    inviter = session.get(User, invite.invited_by)
    authorize_grant(session, inviter, patient, invite.role, invite.scopes)
    return invite, patient


def accept_invite(session, actor, token):
    invite, patient = valid_invite(session, actor, token, lock=True)
    if invite.role == 'primary' and session.scalar(select(Membership.id).where(
            Membership.patient_id == patient.id, Membership.role == 'primary', Membership.revoked_at.is_(None))):
        raise HTTPException(409, 'A primary caregiver is already active')
    member = session.scalar(select(Membership).where(Membership.patient_id == patient.id, Membership.user_id == actor.id))
    if member and member.revoked_at is None:
        raise HTTPException(409, 'You already belong to this care circle')
    if not member:
        member = Membership(patient_id=patient.id, user_id=actor.id)
        session.add(member)
    member.role, member.scopes = invite.role, invite.scopes
    member.accepted_at, member.revoked_at = utcnow(), None
    invite.accepted_at = utcnow()
    session.flush()
    audit(session, actor, patient, 'circle.invitation_accepted_with_consent', member)
    return patient


def change_member(session, actor, patient_id, member_id, grant=None):
    patient = locked_patient(session, patient_id)
    permissions.require(session, actor.id, patient.id, Scope.CIRCLE_MANAGE)
    member = session.get(Membership, str(member_id))
    if not member or member.patient_id != patient.id:
        raise HTTPException(404, 'Member not found')
    if member.user_id == actor.id:
        raise HTTPException(409, 'Ask the patient to change your access; self-removal is not supported')
    if member.role == 'primary' and patient.user_id != actor.id:
        raise HTTPException(403, 'Only the patient can change the primary caregiver')
    if grant:
        if member.revoked_at:
            raise HTTPException(409, 'Invite this person again to restore access with consent')
        scopes = [scope.value for scope in grant.scopes]
        authorize_grant(session, actor, patient, grant.role, scopes)
        if grant.role == 'primary' and session.scalar(select(Membership.id).where(
                Membership.patient_id == patient.id, Membership.role == 'primary',
                Membership.revoked_at.is_(None), Membership.id != member.id)):
            raise HTTPException(409, 'A primary caregiver is already active')
        member.role, member.scopes = grant.role, scopes
    else:
        member.revoked_at = member.revoked_at or utcnow()
    # Scope changes also invalidate delegated invitations and unsent deliveries.
    session.execute(update(Invite).where(Invite.patient_id == patient.id, Invite.invited_by == member.user_id,
                    Invite.accepted_at.is_(None), Invite.revoked_at.is_(None)).values(revoked_at=utcnow()))
    session.execute(update(Delivery).where(Delivery.patient_id == patient.id, Delivery.recipient_user_id == member.user_id,
                    Delivery.status.in_(['pending', 'sending'])).values(status='suppressed'))
    audit(session, actor, patient, 'circle.access_changed' if grant else 'circle.access_revoked', member)
    session.flush()
    return member
