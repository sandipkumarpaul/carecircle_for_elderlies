
"""Stores scheduled medicine doses."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    ForeignKey,
    String,
    Numeric,
    Integer,
    UniqueConstraint,
    CheckConstraint,
    Index,
    text
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.identity import Base, Entity, UTCDateTime


class DoseEvent(Entity, Base):
    __tablename__ = "dose_events"

    __table_args__ = (
        UniqueConstraint(
            "prescription_item_id",
            "scheduled_at",
            name="uq_dose_item_time"
        ),

        Index(
            "ix_dose_events_status_scheduled",
            "status",
            "scheduled_at"
        ),

        CheckConstraint(
            "status IN ('pending', 'taken', 'skipped', 'missed', 'cancelled')",
            name="ck_dose_status"
        )
    )

    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.id"), index=True
    )

    prescription_item_id: Mapped[str] = mapped_column(
        ForeignKey("prescription_items.id")
    )

    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime())

    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3))

    unit: Mapped[str] = mapped_column(String(16))

    status: Mapped[str] = mapped_column(
        String(16), default="pending"
    )

    grace_until: Mapped[datetime] = mapped_column(UTCDateTime())

    snoozed_until: Mapped[datetime | None] = mapped_column(
        UTCDateTime()
    )

    snooze_count: Mapped[int] = mapped_column(
    Integer,
    default=0,
    server_default=text("0")
)
