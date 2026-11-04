"""Sandip sprint 1 identity care circle and alert foundation"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME


revision = '0001_sandip'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Reviewed MySQL 8.4 schema snapshot; independent of future ORM changes.
    op.create_table('auth_rate_buckets',
    sa.Column('key', sa.CHAR(length=64), nullable=False),
    sa.Column('hits', sa.Integer(), nullable=False),
    sa.Column('expires_at', DATETIME(fsp=6), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_index(op.f('ix_auth_rate_buckets_expires_at'), 'auth_rate_buckets', ['expires_at'], unique=False)
    op.create_table('users',
    sa.Column('email_normalized', sa.String(length=254), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('display_name', sa.String(length=100), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('is_admin', sa.Boolean(), nullable=False),
    sa.Column('disabled_at', DATETIME(fsp=6), nullable=True),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email_normalized')
    )
    op.create_table('auth_sessions',
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('token_id_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('csrf_token_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('expires_at', DATETIME(fsp=6), nullable=False),
    sa.Column('revoked_at', DATETIME(fsp=6), nullable=True),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_id_hash')
    )
    op.create_index(op.f('ix_auth_sessions_user_id'), 'auth_sessions', ['user_id'], unique=False)
    op.create_table('patients',
    sa.Column('user_id', sa.CHAR(length=36), nullable=True),
    sa.Column('display_name', sa.String(length=100), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('consent_recorded_at', DATETIME(fsp=6), nullable=False),
    sa.Column('consent_recorded_by', sa.CHAR(length=36), nullable=False),
    sa.Column('consent_basis', sa.String(length=300), nullable=False),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['consent_recorded_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('alerts',
    sa.Column('patient_id', sa.CHAR(length=36), nullable=False),
    sa.Column('type', sa.String(length=40), nullable=False),
    sa.Column('severity', sa.String(length=16), nullable=False),
    sa.Column('source_type', sa.String(length=40), nullable=False),
    sa.Column('source_id', sa.CHAR(length=36), nullable=False),
    sa.Column('dedupe_key', sa.String(length=160), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('patient_id', 'dedupe_key', name='uq_alert_dedupe')
    )
    op.create_index(op.f('ix_alerts_patient_id'), 'alerts', ['patient_id'], unique=False)
    op.create_table('audit_events',
    sa.Column('patient_id', sa.CHAR(length=36), nullable=True),
    sa.Column('actor_user_id', sa.CHAR(length=36), nullable=True),
    sa.Column('action', sa.String(length=60), nullable=False),
    sa.Column('resource_type', sa.String(length=40), nullable=False),
    sa.Column('resource_id', sa.CHAR(length=36), nullable=False),
    sa.Column('occurred_at', DATETIME(fsp=6), nullable=False),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_events_patient_id'), 'audit_events', ['patient_id'], unique=False)
    op.create_table('circle_invites',
    sa.Column('patient_id', sa.CHAR(length=36), nullable=False),
    sa.Column('email_normalized', sa.String(length=254), nullable=False),
    sa.Column('token_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('scopes', sa.JSON(), nullable=False),
    sa.Column('expires_at', DATETIME(fsp=6), nullable=False),
    sa.Column('accepted_at', DATETIME(fsp=6), nullable=True),
    sa.Column('revoked_at', DATETIME(fsp=6), nullable=True),
    sa.Column('invited_by', sa.CHAR(length=36), nullable=False),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.CheckConstraint("role IN ('primary','secondary')", name='ck_invite_role'),
    sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_circle_invites_patient_id'), 'circle_invites', ['patient_id'], unique=False)
    op.create_table('circle_memberships',
    sa.Column('patient_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('scopes', sa.JSON(), nullable=False),
    sa.Column('accepted_at', DATETIME(fsp=6), nullable=True),
    sa.Column('revoked_at', DATETIME(fsp=6), nullable=True),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.CheckConstraint("role IN ('primary','secondary')", name='ck_member_role'),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('patient_id', 'user_id', name='uq_membership_patient_user')
    )
    op.create_index(op.f('ix_circle_memberships_patient_id'), 'circle_memberships', ['patient_id'], unique=False)
    op.create_index(op.f('ix_circle_memberships_user_id'), 'circle_memberships', ['user_id'], unique=False)
    op.create_table('alert_recipients',
    sa.Column('alert_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('read_at', DATETIME(fsp=6), nullable=True),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('alert_id', 'user_id', name='uq_alert_user')
    )
    op.create_table('notification_deliveries',
    sa.Column('patient_id', sa.CHAR(length=36), nullable=False),
    sa.Column('alert_recipient_id', sa.CHAR(length=36), nullable=False),
    sa.Column('recipient_user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('channel', sa.String(length=20), nullable=False),
    sa.Column('template_key', sa.String(length=60), nullable=False),
    sa.Column('dedupe_key', sa.String(length=200), nullable=False),
    sa.Column('due_at', DATETIME(fsp=6), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['alert_recipient_id'], ['alert_recipients.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dedupe_key')
    )
    op.create_index(op.f('ix_notification_deliveries_patient_id'), 'notification_deliveries', ['patient_id'], unique=False)
    

def downgrade():
    # Reviewed MySQL 8.4 schema snapshot; independent of future ORM changes.
    op.drop_index(op.f('ix_notification_deliveries_patient_id'), table_name='notification_deliveries')
    op.drop_table('notification_deliveries')
    op.drop_table('alert_recipients')
    op.drop_index(op.f('ix_circle_memberships_user_id'), table_name='circle_memberships')
    op.drop_index(op.f('ix_circle_memberships_patient_id'), table_name='circle_memberships')
    op.drop_table('circle_memberships')
    op.drop_index(op.f('ix_circle_invites_patient_id'), table_name='circle_invites')
    op.drop_table('circle_invites')
    op.drop_index(op.f('ix_audit_events_patient_id'), table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_index(op.f('ix_alerts_patient_id'), table_name='alerts')
    op.drop_table('alerts')
    op.drop_table('patients')
    op.drop_index(op.f('ix_auth_sessions_user_id'), table_name='auth_sessions')
    op.drop_table('auth_sessions')
    op.drop_table('users')
    op.drop_index(op.f('ix_auth_rate_buckets_expires_at'), table_name='auth_rate_buckets')
    op.drop_table('auth_rate_buckets')
    
