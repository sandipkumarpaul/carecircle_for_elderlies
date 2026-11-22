"""Validated input for CC-14. Authorization lives in the controller."""
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.schemas.contracts import Contract

FUTURE_TOLERANCE_HOURS = 1
MAX_CHECKLIST_ITEMS = 20


class ChecklistItem(Contract):
    text: str = Field(min_length=1, max_length=200)
    done: bool = False


class AppointmentCreate(Contract):
    clinician_label: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)
    scheduled_at: AwareDatetime
    timezone: str = Field(min_length=1, max_length=64)
    checklist: list[ChecklistItem] = Field(default_factory=list, max_length=MAX_CHECKLIST_ITEMS)

    @model_validator(mode='after')
    def validate_timezone(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Use an IANA timezone, e.g. Asia/Dhaka')
        return self


class AppointmentUpdate(Contract):
    clinician_label: str | None = Field(default=None, min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)
    scheduled_at: AwareDatetime | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    checklist: list[ChecklistItem] | None = Field(default=None, max_length=MAX_CHECKLIST_ITEMS)

    @model_validator(mode='after')
    def at_least_one(self):
        if all(v is None for v in self.model_dump().values()):
            raise ValueError('Provide at least one field to update')
        if self.timezone is not None:
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
            try:
                ZoneInfo(self.timezone)
            except (ZoneInfoNotFoundError, ValueError):
                raise ValueError('Use an IANA timezone, e.g. Asia/Dhaka')
        return self


class CancelInput(Contract):
    reason: str | None = Field(default=None, max_length=500)


class CompleteInput(Contract):
    post_visit_prompt: bool = True   # whether to show prescription upload prompt
