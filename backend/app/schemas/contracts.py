"""Shared v1 payload definitions. These validate shape, not authorization/DB state."""
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Scope(StrEnum):
    MEDICINES_READ = "medicines:read"
    MEDICINES_WRITE = "medicines:write"
    ADHERENCE_READ = "adherence:read"
    ADHERENCE_WRITE = "adherence:write"
    VITALS_READ = "vitals:read"
    VITALS_WRITE = "vitals:write"
    SYMPTOMS_READ = "symptoms:read"
    SYMPTOMS_WRITE = "symptoms:write"
    APPOINTMENTS_READ = "appointments:read"
    APPOINTMENTS_WRITE = "appointments:write"
    TASKS_READ = "tasks:read"
    TASKS_WRITE = "tasks:write"
    ALERTS_READ = "alerts:read"
    ALERTS_WRITE = "alerts:write"
    LOCATION_READ = "location:read"
    SUMMARY_READ = "summary:read"
    SUMMARY_CREATE = "summary:create"
    CIRCLE_MANAGE = "circle:manage"
    PRIVACY_MANAGE = "privacy:manage"


class PrescriptionItemInput(Contract):
    medicine_id: UUID
    quantity_per_dose: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    unit: Literal["tablet", "capsule", "ml", "drop", "puff", "unit"]
    start_date: date
    end_date: date | None = None
    schedule_kind: Literal["fixed_times", "as_needed"]
    times_local: list[str] = Field(default_factory=list, max_length=6)
    timezone: str
    meal_relation: Literal["none", "before_meal", "after_meal"] = "none"
    instructions: str | None = Field(default=None, max_length=1000)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Use an IANA timezone, e.g. Asia/Dhaka") from exc
        return value

    @field_validator("times_local")
    @classmethod
    def valid_times(cls, values: list[str]) -> list[str]:
        for value in values:
            try:
                parsed = datetime.strptime(value, "%H:%M")
            except ValueError as exc:
                raise ValueError("Times must be HH:MM") from exc
            if parsed.strftime("%H:%M") != value:
                raise ValueError("Times must be zero-padded HH:MM")
        if len(values) != len(set(values)):
            raise ValueError("Duplicate local times are not allowed")
        return sorted(values)

    @model_validator(mode="after")
    def consistent_schedule(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.schedule_kind == "fixed_times" and not self.times_local:
            raise ValueError("Fixed schedules need explicit times")
        if self.schedule_kind == "as_needed" and self.times_local:
            raise ValueError("As-needed items cannot have scheduled times")
        return self


class RegenerateScheduleCommand(Contract):
    patient_id: UUID
    prescription_id: UUID
    previous_version_id: UUID | None = None
    new_version_id: UUID | None = None
    effective_from: AwareDatetime

    @model_validator(mode="after")
    def needs_version(self):
        if self.previous_version_id is None and self.new_version_id is None:
            raise ValueError("At least one version is required")
        if self.previous_version_id == self.new_version_id:
            raise ValueError("A revision must identify a different new version")
        return self


class RecordAdherenceCommand(Contract):
    """Internal only: controller/worker supplies trusted actor and action context."""
    patient_id: UUID
    dose_event_id: UUID
    actor_user_id: UUID | None
    action: Literal["taken", "skipped", "snoozed", "missed"]
    occurred_at: AwareDatetime
    idempotency_key: UUID

    @model_validator(mode="after")
    def actor_context(self):
        if self.action == "missed" and self.actor_user_id is not None:
            raise ValueError("Missed is a system-only action")
        if self.action != "missed" and self.actor_user_id is None:
            raise ValueError("Patient/caregiver action needs an actor")
        return self


class RaiseAlertCommand(Contract):
    patient_id: UUID
    type: Literal["missed_dose", "vital_threshold", "vital_trend", "low_stock",
                  "stock_reconciliation", "sos", "checkin_missed", "prescription_changed",
                  "possible_side_effect", "adherence_risk", "task_due"]
    severity: Literal["info", "warning", "critical"]
    source_type: Literal["dose_event", "vital", "stock", "sos_event", "checkin",
                         "prescription_version", "symptom", "risk_prediction", "task"]
    source_id: UUID
    dedupe_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9:_-]+$")
