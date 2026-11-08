
"""Generate scheduled dose events for confirmed prescriptions."""

from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.medicines import PrescriptionItem, PrescriptionVersion
from app.models.doses import DoseEvent
from app.schemas.contracts import RegenerateScheduleCommand


def local_time_to_utc(day: date, clock: time, zone: ZoneInfo) -> datetime:
    """Convert local date and time to UTC, handling daylight saving time."""

    local = datetime.combine(day, clock)

    # Use the first occurrence when a local time happens twice.
    candidate = local.replace(tzinfo=zone, fold=0)

    # Check whether this local time actually exists.
    returned = candidate.astimezone(timezone.utc).astimezone(zone)

    if returned.replace(tzinfo=None) != local:
        # A nonexistent time moves forward by the DST gap.
        first_offset = local.replace(tzinfo=zone, fold=0).utcoffset()
        second_offset = local.replace(tzinfo=zone, fold=1).utcoffset()
        gap = second_offset - first_offset

        candidate = (local + gap).replace(tzinfo=zone, fold=0)

    return candidate.astimezone(timezone.utc)


class ScheduleService:

    def regenerate(
        self,
        session: Session,
        command: RegenerateScheduleCommand,
        now: datetime,
    ) -> None:

        if now.tzinfo is None or command.effective_from.tzinfo is None:
            raise ValueError("Timezone-aware datetimes are required")

        effective_from = command.effective_from.astimezone(timezone.utc)
        now_utc = now.astimezone(timezone.utc)

        if effective_from < now_utc:
            raise ValueError("Retroactive schedule changes are not allowed")

        # Validate that the versions belong to this patient and prescription.
        previous_version = None
        new_version = None

        for version_id in (
            command.previous_version_id,
            command.new_version_id,
        ):
            if version_id is None:
                continue

            version = session.get(PrescriptionVersion, str(version_id))

            if (
                version is None
                or version.patient_id != str(command.patient_id)
                or version.prescription_id != str(command.prescription_id)
            ):
                raise ValueError(
                    "Prescription version does not belong to this patient"
                )

            if version_id == command.previous_version_id:
                previous_version = version

            if version_id == command.new_version_id:
                new_version = version

        # The previous version must already be confirmed.
        if previous_version is not None:
            if previous_version.status != "confirmed":
                raise ValueError("Previous prescription version is not confirmed")

        # The new version must be confirmed and use the requested effective time.
        if new_version is not None:
            if new_version.status != "confirmed":
                raise ValueError("New prescription version is not confirmed")

            if (
                new_version.effective_from.astimezone(timezone.utc)
                != effective_from
            ):
                raise ValueError(
                    "New version effective time does not match the command"
                )

        # Cancel pending old events from the effective time onward.
        if previous_version is not None:

            old_items = select(PrescriptionItem.id).where(
                PrescriptionItem.prescription_version_id
                == str(command.previous_version_id)
            )

            old_events = session.scalars(
                select(DoseEvent).where(
                    DoseEvent.prescription_item_id.in_(old_items),
                    DoseEvent.patient_id == str(command.patient_id),
                    DoseEvent.scheduled_at >= effective_from,
                    DoseEvent.status == "pending",
                )
            )

            for event in old_events:
                event.status = "cancelled"

        # No new version means the prescription is being stopped.
        if new_version is None:
            session.flush()
            return

        new_items = session.scalars(
            select(PrescriptionItem).where(
                PrescriptionItem.prescription_version_id
                == str(command.new_version_id),
                PrescriptionItem.patient_id == str(command.patient_id),
            )
        ).all()

        # Generate today's events and the next 13 days.
        for item in new_items:

            # As-needed medicines do not get automatic events.
            if item.schedule_kind == "as_needed":
                continue

            zone = ZoneInfo(item.timezone)

            today = now_utc.astimezone(zone).date()
            effective_day = effective_from.astimezone(zone).date()

            first_day = max(item.start_date, today, effective_day)
            last_day = today + timedelta(days=13)

            if item.end_date is not None:
                last_day = min(last_day, item.end_date)

            if first_day > last_day:
                continue

            for day_number in range((last_day - first_day).days + 1):

                current_day = first_day + timedelta(days=day_number)

                for local_text in item.times_local:

                    clock = time.fromisoformat(local_text)

                    scheduled_at = local_time_to_utc(
                        current_day,
                        clock,
                        zone,
                    )

                    # Do not create events before the version starts
                    # or for times that have already passed.
                    if scheduled_at < effective_from or scheduled_at < now_utc:
                        continue

                    # Check whether this event already exists.
                    existing = session.scalar(
                        select(DoseEvent.id).where(
                            DoseEvent.prescription_item_id == item.id,
                            DoseEvent.scheduled_at == scheduled_at,
                        )
                    )

                    if existing is not None:
                        continue

                    event = DoseEvent(
                        patient_id=item.patient_id,
                        prescription_item_id=item.id,
                        scheduled_at=scheduled_at,
                        quantity=item.quantity_per_dose,
                        unit=item.unit,
                        status="pending",
                        grace_until=scheduled_at + timedelta(minutes=30),
                    )

                    session.add(event)

        # The caller controls the database transaction.
        session.flush()
