"""Saif CC-12 vitals readings and per-patient thresholds"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME


revision = '0003_saif'
down_revision = '0002_tanjila'
branch_labels = None
depends_on = None


def upgrade():
    # Reviewed schema snapshot; independent of future ORM changes. Purely additive.
    op.create_table('vitals',
    sa.Column('patient_id', sa.CHAR(length=36), nullable=False),
    sa.Column('recorded_by', sa.CHAR(length=36), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('value', sa.Numeric(precision=7, scale=2), nullable=False),
    sa.Column('secondary_value', sa.Numeric(precision=7, scale=2), nullable=True),
    sa.Column('unit', sa.String(length=16), nullable=False),
    sa.Column('observed_at', DATETIME(fsp=6), nullable=False),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('patient_id', 'kind', 'observed_at', name='uq_vital_patient_kind_time')
    )
    op.create_index(op.f('ix_vitals_patient_id'), 'vitals', ['patient_id'], unique=False)
    op.create_index('ix_vitals_patient_kind_time', 'vitals', ['patient_id', 'kind', 'observed_at'], unique=False)
    op.create_table('vital_thresholds',
    sa.Column('patient_id', sa.CHAR(length=36), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('unit', sa.String(length=16), nullable=False),
    sa.Column('lower', sa.Numeric(precision=7, scale=2), nullable=True),
    sa.Column('upper', sa.Numeric(precision=7, scale=2), nullable=True),
    sa.Column('secondary_lower', sa.Numeric(precision=7, scale=2), nullable=True),
    sa.Column('secondary_upper', sa.Numeric(precision=7, scale=2), nullable=True),
    sa.Column('trend_rule', sa.JSON(), nullable=True),
    sa.Column('updated_by', sa.CHAR(length=36), nullable=False),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('patient_id', 'kind', name='uq_threshold_patient_kind')
    )
    op.create_index(op.f('ix_vital_thresholds_patient_id'), 'vital_thresholds', ['patient_id'], unique=False)


def downgrade():
    # Destroys all recorded vitals and thresholds. Dropping the tables also drops their indexes
    # (MySQL refuses to drop an index that a foreign key still needs, so do not drop them first).
    op.drop_table('vital_thresholds')
    op.drop_table('vitals')
