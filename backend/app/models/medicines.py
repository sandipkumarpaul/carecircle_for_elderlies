"""Reference data and the minimum immutable medication record for CC-03/04."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CHAR, Date, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.identity import Base, Entity, UTCDateTime


class ReferenceRevision(Base):
    __tablename__ = 'reference_revision'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)


class Medicine(Entity, Base):
    __tablename__ = 'medicines'
    generic_name: Mapped[str] = mapped_column(String(160))
    brand_name: Mapped[str] = mapped_column(String(160))
    strength: Mapped[str] = mapped_column(String(60))
    form: Mapped[str] = mapped_column(String(30))
    normalized_key: Mapped[str] = mapped_column(CHAR(64), unique=True)
    source_name: Mapped[str] = mapped_column(String(300))
    source_license: Mapped[str] = mapped_column(String(200))


class InteractionRule(Entity, Base):
    __tablename__ = 'interaction_rules'
    __table_args__ = (UniqueConstraint('medicine_a_id', 'medicine_b_id', name='uq_interaction_pair'),)
    medicine_a_id: Mapped[str] = mapped_column(ForeignKey('medicines.id'))
    medicine_b_id: Mapped[str] = mapped_column(ForeignKey('medicines.id'))
    severity: Mapped[str] = mapped_column(String(16))
    explanation: Mapped[str] = mapped_column(String(1000))
    source: Mapped[str] = mapped_column(String(300))


class Prescription(Entity, Base):
    __tablename__ = 'prescriptions'
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))


class PrescriptionVersion(Entity, Base):
    __tablename__ = 'prescription_versions'
    __table_args__ = (UniqueConstraint('prescription_id', 'version_number', name='uq_prescription_version'),)
    prescription_id: Mapped[str] = mapped_column(ForeignKey('prescriptions.id'))
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    effective_from: Mapped[datetime] = mapped_column(UTCDateTime())
    effective_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    confirmed_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    confirmed_at: Mapped[datetime] = mapped_column(UTCDateTime())
    schedule_status: Mapped[str] = mapped_column(String(30), default='not_integrated')
    previous_version_id: Mapped[str | None] = mapped_column(ForeignKey('prescription_versions.id'))
    change_reason: Mapped[str | None] = mapped_column(String(1000))
    ocr_draft_id: Mapped[str | None] = mapped_column(ForeignKey('ocr_drafts.id'))


class PrescriptionItem(Entity, Base):
    __tablename__ = 'prescription_items'
    prescription_version_id: Mapped[str] = mapped_column(ForeignKey('prescription_versions.id'))
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'), index=True)
    medicine_id: Mapped[str] = mapped_column(ForeignKey('medicines.id'))
    quantity_per_dose: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    unit: Mapped[str] = mapped_column(String(16))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    schedule_kind: Mapped[str] = mapped_column(String(20))
    times_local: Mapped[list] = mapped_column(JSON)
    timezone: Mapped[str] = mapped_column(String(64))
    meal_relation: Mapped[str] = mapped_column(String(20))
    instructions: Mapped[str | None] = mapped_column(String(1000))


class WarningCheck(Entity, Base):
    __tablename__ = 'warning_checks'
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'), index=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    proposed_items: Mapped[list] = mapped_column(JSON)
    warnings: Mapped[list] = mapped_column(JSON)
    state_hash: Mapped[str] = mapped_column(CHAR(64))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    confirmed_version_id: Mapped[str | None] = mapped_column(ForeignKey('prescription_versions.id'), unique=True)
    replaces_version_id: Mapped[str | None] = mapped_column(ForeignKey('prescription_versions.id'))
    change_reason: Mapped[str | None] = mapped_column(String(1000))
    ocr_draft_id: Mapped[str | None] = mapped_column(ForeignKey('ocr_drafts.id'))


class OcrDraft(Entity, Base):
    __tablename__ = 'ocr_drafts'
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'), index=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    raw_text: Mapped[str] = mapped_column(Text)
    reviewed_text: Mapped[str] = mapped_column(Text)
    recognition_status: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    edit_revision: Mapped[int] = mapped_column(Integer, default=0)
