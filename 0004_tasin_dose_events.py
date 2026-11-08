"""Tasin CC-06 scheduled dose events"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME


revision = '0004_tasin'
down_revision = '0003_saif'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'dose_events',

        sa.Column('patient_id', sa.CHAR(length=36), nullable=False),
        sa.Column('prescription_item_id', sa.CHAR(length=36), nullable=False),

        sa.Column('scheduled_at', DATETIME(fsp=6), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column('unit', sa.String(length=16), nullable=False),

        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('grace_until', DATETIME(fsp=6), nullable=False),
        sa.Column('snoozed_until', DATETIME(fsp=6), nullable=True),
        sa.Column(
                'snooze_count',
                sa.Integer(),
                server_default=sa.text('0'),
                nullable=False
            ),

        sa.Column('id', sa.CHAR(length=36), nullable=False),
        sa.Column('created_at', DATETIME(fsp=6), nullable=False),
        sa.Column('updated_at', DATETIME(fsp=6), nullable=False),

        sa.ForeignKeyConstraint(['patient_id'], ['patients.id']),
        sa.ForeignKeyConstraint(
            ['prescription_item_id'],
            ['prescription_items.id']
        ),

        sa.PrimaryKeyConstraint('id'),

        sa.UniqueConstraint(
            'prescription_item_id',
            'scheduled_at',
            name='uq_dose_item_time'
        ),

        sa.CheckConstraint(
            "status IN ('pending', 'taken', 'skipped', 'missed', 'cancelled')",
            name='ck_dose_status'
        )
    )

    op.create_index(
        op.f('ix_dose_events_patient_id'),
        'dose_events',
        ['patient_id'],
        unique=False
    )

    op.create_index(
        'ix_dose_events_status_scheduled',
        'dose_events',
        ['status', 'scheduled_at'],
        unique=False
    )


def downgrade():
    op.drop_table('dose_events')