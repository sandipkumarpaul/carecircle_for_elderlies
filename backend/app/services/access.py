from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Membership, Patient, User
from app.schemas.contracts import Scope

ALL_SCOPES = {scope.value for scope in Scope}


def expanded(scopes):
    result = set(scopes)
    for scope in list(result):
        if scope.endswith(':write'):
            result.add(scope.replace(':write', ':read'))
    return result


class PermissionService:
    def context(self, session, actor_user_id, patient_id):
        user = session.get(User, str(actor_user_id))
        patient = session.get(Patient, str(patient_id))
        if not user or user.disabled_at or not patient:
            raise HTTPException(404, 'Patient not found')
        if patient.user_id == user.id:
            return patient, 'patient', ALL_SCOPES.copy()
        member = session.scalar(select(Membership).where(
            Membership.patient_id == patient.id, Membership.user_id == user.id,
            Membership.accepted_at.is_not(None), Membership.revoked_at.is_(None)))
        if not member:
            raise HTTPException(404, 'Patient not found')
        return patient, member.role, expanded(member.scopes)

    def require(self, session, actor_user_id: UUID, patient_id: UUID, scope: Scope):
        _, _, scopes = self.context(session, actor_user_id, patient_id)
        if scope.value not in scopes:
            raise HTTPException(403, 'Your care-circle access does not allow this action')


permissions = PermissionService()
