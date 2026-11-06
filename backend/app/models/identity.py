from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CHAR, CheckConstraint, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def utcnow():
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DATETIME(fsp=6)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError('An aware datetime is required')
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value else None


class Base(DeclarativeBase):
    pass


class Entity:
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class User(Entity, Base):
    __tablename__ = 'users'
    email_normalized: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(64), default='Asia/Dhaka')
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class AuthSession(Entity, Base):
    __tablename__ = 'auth_sessions'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    token_id_hash: Mapped[str] = mapped_column(CHAR(64), unique=True)
    csrf_token_hash: Mapped[str] = mapped_column(CHAR(64))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Patient(Entity, Base):
    __tablename__ = 'patients'
    user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(64))
    consent_recorded_at: Mapped[datetime] = mapped_column(UTCDateTime())
    consent_recorded_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    consent_basis: Mapped[str] = mapped_column(String(300))
    allergies: Mapped[list] = mapped_column(JSON, default=list)


class Membership(Entity, Base):
    __tablename__ = 'circle_memberships'
    __table_args__ = (UniqueConstraint('patient_id', 'user_id', name='uq_membership_patient_user'),
                      CheckConstraint("role IN ('primary','secondary')", name='ck_member_role'))
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    role: Mapped[str] = mapped_column(String(16))
    scopes: Mapped[list] = mapped_column(JSON)
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Invite(Entity, Base):
    __tablename__ = 'circle_invites'
    __table_args__ = (CheckConstraint("role IN ('primary','secondary')", name='ck_invite_role'),)
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'), index=True)
    email_normalized: Mapped[str] = mapped_column(String(254))
    token_hash: Mapped[str] = mapped_column(CHAR(64), unique=True)
    role: Mapped[str] = mapped_column(String(16))
    scopes: Mapped[list] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    invited_by: Mapped[str] = mapped_column(ForeignKey('users.id'))


class AuditEvent(Entity, Base):
    __tablename__ = 'audit_events'
    patient_id: Mapped[str | None] = mapped_column(ForeignKey('patients.id'), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(60))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str] = mapped_column(CHAR(36))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Alert(Entity, Base):
    __tablename__ = 'alerts'
    __table_args__ = (UniqueConstraint('patient_id', 'dedupe_key', name='uq_alert_dedupe'),)
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'), index=True)
    type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(16))
    source_type: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str] = mapped_column(CHAR(36))
    dedupe_key: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default='open')


class AlertRecipient(Entity, Base):
    __tablename__ = 'alert_recipients'
    __table_args__ = (UniqueConstraint('alert_id', 'user_id', name='uq_alert_user'),)
    alert_id: Mapped[str] = mapped_column(ForeignKey('alerts.id'))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Delivery(Entity, Base):
    __tablename__ = 'notification_deliveries'
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'), index=True)
    alert_recipient_id: Mapped[str] = mapped_column(ForeignKey('alert_recipients.id'))
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    channel: Mapped[str] = mapped_column(String(20), default='in_app')
    template_key: Mapped[str] = mapped_column(String(60))
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    due_at: Mapped[datetime] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(String(20), default='pending')


class RateBucket(Base):
    __tablename__ = 'auth_rate_buckets'
    key: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    hits: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
