"""Saif CC-14 appointment tracker and visit follow-up"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = '0007_saif_appointments'
down_revision = '0006_tanjila'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('appointments',
    sa.Column('patient_id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_by', sa.CHAR(length=36), nullable=False),
    sa.Column('clinician_label', sa.String(length=200), nullable=False),
    sa.Column('location', sa.String(length=300), nullable=True),
    sa.Column('notes', sa.String(length=1000), nullable=True),
    sa.Column('scheduled_at', DATETIME(fsp=6), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('checklist', sa.JSON(), nullable=True),
    sa.Column('completed_at', DATETIME(fsp=6), nullable=True),
    sa.Column('cancelled_at', DATETIME(fsp=6), nullable=True),
    sa.Column('cancelled_reason', sa.String(length=500), nullable=True),
    sa.Column('post_visit_prompt_at', DATETIME(fsp=6), nullable=True),
    sa.Column('post_visit_dismissed_at', DATETIME(fsp=6), nullable=True),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id']),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_appointments_patient_id'), 'appointments', ['patient_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_appointments_patient_id'), table_name='appointments')
    op.drop_table('appointments')
