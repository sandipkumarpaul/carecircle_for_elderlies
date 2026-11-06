"""Tanjila medicine reference and warning review"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME


revision = '0002_tanjila'
down_revision = '0001_sandip'
branch_labels = None
depends_on = None

def upgrade():
    # Reviewed schema snapshot; independent of future ORM changes.
    op.create_table('medicines',
    sa.Column('generic_name', sa.String(length=160), nullable=False),
    sa.Column('brand_name', sa.String(length=160), nullable=False),
    sa.Column('strength', sa.String(length=60), nullable=False),
    sa.Column('form', sa.String(length=30), nullable=False),
    sa.Column('normalized_key', sa.CHAR(length=64), nullable=False),
    sa.Column('source_name', sa.String(length=300), nullable=False),
    sa.Column('source_license', sa.String(length=200), nullable=False),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('normalized_key')
    )
    op.create_table('reference_revision',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('interaction_rules',
    sa.Column('medicine_a_id', sa.CHAR(length=36), nullable=False),
    sa.Column('medicine_b_id', sa.CHAR(length=36), nullable=False),
    sa.Column('severity', sa.String(length=16), nullable=False),
    sa.Column('explanation', sa.String(length=1000), nullable=False),
    sa.Column('source', sa.String(length=300), nullable=False),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['medicine_a_id'], ['medicines.id'], ),
    sa.ForeignKeyConstraint(['medicine_b_id'], ['medicines.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('medicine_a_id', 'medicine_b_id', name='uq_interaction_pair')
    )
    op.create_table('prescriptions',
    sa.Column('patient_id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_by', sa.CHAR(length=36), nullable=False),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prescriptions_patient_id'), 'prescriptions', ['patient_id'], unique=False)
    op.create_table('prescription_versions',
    sa.Column('prescription_id', sa.CHAR(length=36), nullable=False),
    sa.Column('patient_id', sa.CHAR(length=36), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('effective_from', DATETIME(fsp=6), nullable=False),
    sa.Column('effective_until', DATETIME(fsp=6), nullable=True),
    sa.Column('confirmed_by', sa.CHAR(length=36), nullable=False),
    sa.Column('confirmed_at', DATETIME(fsp=6), nullable=False),
    sa.Column('schedule_status', sa.String(length=30), nullable=False),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['confirmed_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['prescription_id'], ['prescriptions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('prescription_id', 'version_number', name='uq_prescription_version')
    )
    op.create_index(op.f('ix_prescription_versions_patient_id'), 'prescription_versions', ['patient_id'], unique=False)
    op.create_table('prescription_items',
    sa.Column('prescription_version_id', sa.CHAR(length=36), nullable=False),
    sa.Column('patient_id', sa.CHAR(length=36), nullable=False),
    sa.Column('medicine_id', sa.CHAR(length=36), nullable=False),
    sa.Column('quantity_per_dose', sa.Numeric(precision=10, scale=3), nullable=False),
    sa.Column('unit', sa.String(length=16), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('schedule_kind', sa.String(length=20), nullable=False),
    sa.Column('times_local', sa.JSON(), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('meal_relation', sa.String(length=20), nullable=False),
    sa.Column('instructions', sa.String(length=1000), nullable=True),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['medicine_id'], ['medicines.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['prescription_version_id'], ['prescription_versions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prescription_items_patient_id'), 'prescription_items', ['patient_id'], unique=False)
    op.create_table('warning_checks',
    sa.Column('patient_id', sa.CHAR(length=36), nullable=False),
    sa.Column('actor_user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('proposed_items', sa.JSON(), nullable=False),
    sa.Column('warnings', sa.JSON(), nullable=False),
    sa.Column('state_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('expires_at', DATETIME(fsp=6), nullable=False),
    sa.Column('acknowledged_at', DATETIME(fsp=6), nullable=True),
    sa.Column('confirmed_version_id', sa.CHAR(length=36), nullable=True),
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['confirmed_version_id'], ['prescription_versions.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('confirmed_version_id')
    )
    op.create_index(op.f('ix_warning_checks_patient_id'), 'warning_checks', ['patient_id'], unique=False)
    op.add_column('patients', sa.Column('allergies', sa.JSON(), nullable=True))
    op.execute("UPDATE patients SET allergies = JSON_ARRAY()")
    op.alter_column('patients', 'allergies', existing_type=sa.JSON(), nullable=False)
    op.execute('INSERT INTO reference_revision (id, revision) VALUES (1, 0)')
    # ### end Alembic commands ###

def downgrade():
    # Reviewed schema snapshot; independent of future ORM changes.
    op.drop_column('patients', 'allergies')
    op.drop_table('warning_checks')
    op.drop_table('prescription_items')
    op.drop_table('prescription_versions')
    op.drop_table('prescriptions')
    op.drop_table('interaction_rules')
    op.drop_table('reference_revision')
    op.drop_table('medicines')
    # ### end Alembic commands ###
