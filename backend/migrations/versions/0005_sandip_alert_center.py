"""Sandip CC-18 alert lifecycle and recipient quiet hours."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = '0005_sandip'
down_revision = '0004_tasin'
branch_labels = None
depends_on = None


def upgrade():
    for name in ('acknowledged_by', 'resolved_by'):
        op.add_column('alerts', sa.Column(name, sa.CHAR(36), nullable=True))
        op.create_foreign_key('fk_alert_' + name, 'alerts', 'users', [name], ['id'])
    for name in ('acknowledged_at', 'resolved_at'):
        op.add_column('alerts', sa.Column(name, DATETIME(fsp=6), nullable=True))
    op.create_table('alert_preferences',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('patient_id', sa.CHAR(36), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('user_id', sa.CHAR(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('timezone', sa.String(64), nullable=False),
        sa.Column('quiet_start', sa.String(5), nullable=True),
        sa.Column('quiet_end', sa.String(5), nullable=True),
        sa.Column('created_at', DATETIME(fsp=6), nullable=False),
        sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
        sa.UniqueConstraint('patient_id', 'user_id', name='uq_alert_preference'))


def downgrade():
    op.drop_table('alert_preferences')
    for name in ('acknowledged_by', 'resolved_by'):
        op.drop_constraint('fk_alert_' + name, 'alerts', type_='foreignkey')
        op.drop_column('alerts', name)
    for name in ('acknowledged_at', 'resolved_at'):
        op.drop_column('alerts', name)
