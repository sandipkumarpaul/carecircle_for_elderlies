"""Internal contracts; implementations must use caller-owned transaction/session."""
from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app.schemas.contracts import (
    RaiseAlertCommand, RecordAdherenceCommand, RegenerateScheduleCommand, Scope,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class PermissionService(Protocol):
    def require(self, session: "Session", actor_user_id: UUID, patient_id: UUID, scope: Scope) -> None: ...


class AlertService(Protocol):
    def raise_alert(self, session: "Session", command: RaiseAlertCommand, now: datetime) -> UUID: ...


class ScheduleService(Protocol):
    def regenerate(self, session: "Session", command: RegenerateScheduleCommand, now: datetime) -> None: ...


class AdherenceService(Protocol):
    def record(self, session: "Session", command: RecordAdherenceCommand, now: datetime) -> UUID: ...
