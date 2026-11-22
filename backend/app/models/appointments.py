"""CC-14 appointment tracker and visit follow-up (Saif)."""
from datetime import datetime

from sqlalchemy import ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.identity import Base, Entity, UTCDateTime


class Appointment(Entity, Base):
    """One scheduled visit. Status: scheduled → completed or cancelled."""
    __tablename__ = 'appointments'
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    clinician_label: Mapped[str] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(String(1000))
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime())
    timezone: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default='scheduled')   # scheduled|completed|cancelled
    checklist: Mapped[dict | None] = mapped_column(JSON)                   # {items:[{text,done}]}
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    cancelled_reason: Mapped[str | None] = mapped_column(String(500))
    post_visit_prompt_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    post_visit_dismissed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
