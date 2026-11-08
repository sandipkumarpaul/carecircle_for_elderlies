"""CC-12 vitals readings and per-patient thresholds (Saif)."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CHAR, ForeignKey, Index, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.identity import Base, Entity, UTCDateTime


class Vital(Entity, Base):
    """One measurement. Blood pressure uses value=systolic and secondary_value=diastolic."""
    __tablename__ = 'vitals'
    __table_args__ = (
        # A double-submitted form cannot create two identical readings.
        UniqueConstraint('patient_id', 'kind', 'observed_at', name='uq_vital_patient_kind_time'),
        Index('ix_vitals_patient_kind_time', 'patient_id', 'kind', 'observed_at'),
    )
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'), index=True)
    recorded_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(16))          # bp | sugar | weight | spo2
    value: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    secondary_value: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    unit: Mapped[str] = mapped_column(String(16))
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime())


class VitalThreshold(Entity, Base):
    """Per-patient bounds for one kind, plus an optional override of the trend rule."""
    __tablename__ = 'vital_thresholds'
    __table_args__ = (UniqueConstraint('patient_id', 'kind', name='uq_threshold_patient_kind'),)
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    unit: Mapped[str] = mapped_column(String(16))
    lower: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    upper: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    secondary_lower: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    secondary_upper: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    trend_rule: Mapped[dict | None] = mapped_column(JSON)  # null = documented default rule
    updated_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
