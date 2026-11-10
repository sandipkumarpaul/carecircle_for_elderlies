"""Tanjila CC-02 OCR drafts and CC-05 version provenance."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = '0006_tanjila'
down_revision = '0005_sandip'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ocr_drafts',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('patient_id', sa.CHAR(36), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('uploaded_by', sa.CHAR(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('reviewed_text', sa.Text(), nullable=False),
        sa.Column('recognition_status', sa.String(30), nullable=False),
        sa.Column('confidence', sa.Numeric(5, 2), nullable=True),
        sa.Column('reviewed_at', DATETIME(fsp=6), nullable=True),
        sa.Column('reviewed_by', sa.CHAR(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('edit_revision', sa.Integer(), nullable=False),
        sa.Column('created_at', DATETIME(fsp=6), nullable=False),
        sa.Column('updated_at', DATETIME(fsp=6), nullable=False))
    op.create_index('ix_ocr_drafts_patient_id', 'ocr_drafts', ['patient_id'])
    for table in ('prescription_versions', 'warning_checks'):
        op.add_column(table, sa.Column('change_reason', sa.String(1000), nullable=True))
        op.add_column(table, sa.Column('ocr_draft_id', sa.CHAR(36), nullable=True))
        op.create_foreign_key('fk_' + table + '_ocr', table, 'ocr_drafts', ['ocr_draft_id'], ['id'])
    for table, column in (('prescription_versions', 'previous_version_id'), ('warning_checks', 'replaces_version_id')):
        op.add_column(table, sa.Column(column, sa.CHAR(36), nullable=True))
        op.create_foreign_key('fk_' + table + '_previous', table, 'prescription_versions', [column], ['id'])


def downgrade():
    for table, column in (('warning_checks', 'replaces_version_id'), ('prescription_versions', 'previous_version_id')):
        op.drop_constraint('fk_' + table + '_previous', table, type_='foreignkey')
        op.drop_column(table, column)
    for table in ('warning_checks', 'prescription_versions'):
        op.drop_constraint('fk_' + table + '_ocr', table, type_='foreignkey')
        op.drop_column(table, 'ocr_draft_id')
        op.drop_column(table, 'change_reason')
    op.drop_table('ocr_drafts')
