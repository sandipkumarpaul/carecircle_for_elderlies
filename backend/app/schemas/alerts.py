from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class QuietHoursInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    timezone: str
    quiet_start: str | None = None
    quiet_end: str | None = None

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Use a valid IANA timezone')
        return value

    @field_validator('quiet_start', 'quiet_end')
    @classmethod
    def valid_time(cls, value):
        if value is not None:
            if len(value) != 5 or time.fromisoformat(value).isoformat(timespec='minutes') != value:
                raise ValueError('Use HH:MM')
        return value

    @model_validator(mode='after')
    def pair(self):
        if (self.quiet_start is None) != (self.quiet_end is None):
            raise ValueError('Provide both quiet-hour times or neither')
        if self.quiet_start is not None and self.quiet_start == self.quiet_end:
            raise ValueError('Quiet-hour start and end must differ')
        return self
