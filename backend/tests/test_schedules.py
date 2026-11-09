
from datetime import date, datetime, time, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.services.schedules import local_time_to_utc
from app.schemas.contracts import RegenerateScheduleCommand


def test_dhaka_time_converts_to_utc():
    result = local_time_to_utc(
        date(2026, 11, 8),
        time(8, 0),
        ZoneInfo("Asia/Dhaka"),
    )

    assert result == datetime(
        2026, 11, 8, 2, 0, tzinfo=timezone.utc
    )


def test_ambiguous_daylight_saving_time_uses_first_occurrence():
    result = local_time_to_utc(
        date(2026, 11, 1),
        time(1, 30),
        ZoneInfo("America/New_York"),
    )

    assert result == datetime(
        2026, 11, 1, 5, 30, tzinfo=timezone.utc
    )


def test_nonexistent_daylight_saving_time_moves_forward():
    result = local_time_to_utc(
        date(2026, 3, 8),
        time(2, 30),
        ZoneInfo("America/New_York"),
    )

    assert result == datetime(
        2026, 3, 8, 7, 30, tzinfo=timezone.utc
    )


def test_schedule_command_accepts_new_version():
    command = RegenerateScheduleCommand(
        patient_id=uuid4(),
        prescription_id=uuid4(),
        new_version_id=uuid4(),
        effective_from=datetime.now(timezone.utc),
    )

    assert command.new_version_id is not None


def test_schedule_command_rejects_no_versions():
    with pytest.raises(ValidationError):
        RegenerateScheduleCommand(
            patient_id=uuid4(),
            prescription_id=uuid4(),
            effective_from=datetime.now(timezone.utc),
        )


def test_schedule_command_rejects_same_old_and_new_version():
    version_id = uuid4()

    with pytest.raises(ValidationError):
        RegenerateScheduleCommand(
            patient_id=uuid4(),
            prescription_id=uuid4(),
            previous_version_id=version_id,
            new_version_id=version_id,
            effective_from=datetime.now(timezone.utc),
        )
