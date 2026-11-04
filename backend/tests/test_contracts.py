from uuid import uuid4
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.contracts import PrescriptionItemInput, RaiseAlertCommand, RecordAdherenceCommand, RegenerateScheduleCommand


def item(**changes):
    return dict(medicine_id=str(uuid4()), quantity_per_dose="1.000", unit="tablet",
                start_date="2026-11-04", schedule_kind="fixed_times",
                times_local=["20:00", "08:00"], timezone="Asia/Dhaka") | changes


def test_fixed_times_are_canonical_and_decimal_quantity_is_preserved():
    result = PrescriptionItemInput(**item())
    assert result.times_local == ["08:00", "20:00"]
    assert str(result.quantity_per_dose) == "1.000"


@pytest.mark.parametrize("changes", [
    {"times_local": ["08:00", "08:00"]}, {"times_local": ["24:00"]},
    {"times_local": ["8:00"]}, {"times_local": []},
    {"schedule_kind": "as_needed"}, {"timezone": "Not/AZone"},
    {"quantity_per_dose": "0"}, {"quantity_per_dose": "1.0001"},
    {"end_date": "2026-11-03"}, {"actor_user_id": str(uuid4())},
])
def test_invalid_prescription_shapes_fail(changes):
    with pytest.raises(ValidationError):
        PrescriptionItemInput(**item(**changes))


def test_as_needed_has_no_times():
    assert PrescriptionItemInput(**item(schedule_kind="as_needed", times_local=[])).times_local == []


def test_schedule_rejects_naive_time_and_empty_revision():
    data = dict(patient_id=uuid4(), prescription_id=uuid4(), new_version_id=uuid4())
    with pytest.raises(ValidationError):
        RegenerateScheduleCommand(**data, effective_from="2026-11-04T08:00:00")
    data["new_version_id"] = None
    with pytest.raises(ValidationError):
        RegenerateScheduleCommand(**data, effective_from="2026-11-04T08:00:00+06:00")


def test_worker_missed_cannot_be_attributed_to_browser_actor():
    data = dict(patient_id=uuid4(), dose_event_id=uuid4(), actor_user_id=uuid4(),
                action="missed", occurred_at="2026-11-04T08:00:00Z", idempotency_key=uuid4())
    with pytest.raises(ValidationError):
        RecordAdherenceCommand(**data)
    data["actor_user_id"] = None
    assert RecordAdherenceCommand(**data).action == "missed"
    data["action"] = "taken"
    with pytest.raises(ValidationError):
        RecordAdherenceCommand(**data)


def test_shared_examples_remain_valid_for_consumers():
    examples = json.loads((Path(__file__).parent / "fixtures/contracts.json").read_text())
    for name, schema in [("prescription_item", PrescriptionItemInput),
                         ("schedule_command", RegenerateScheduleCommand),
                         ("adherence_command", RecordAdherenceCommand),
                         ("alert_command", RaiseAlertCommand)]:
        schema.model_validate(examples[name])
