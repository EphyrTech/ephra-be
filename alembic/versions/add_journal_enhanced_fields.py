"""Add enhanced journal fields

Revision ID: add_journal_enhanced_fields
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_journal_enhanced_fields'
down_revision = None  # Update this with the latest revision ID
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to journals table
    op.add_column('journals', sa.Column('mood', sa.String(), nullable=True))
    op.add_column('journals', sa.Column('emotions', sa.JSON(), nullable=True))
    op.add_column('journals', sa.Column('sleep', sa.String(), nullable=True))
    op.add_column('journals', sa.Column('quick_note', sa.Text(), nullable=True))
    op.add_column('journals', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('journals', sa.Column('date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('journals', sa.Column('shared_with_coach', sa.Boolean(), nullable=True, default=False))
    op.add_column('journals', sa.Column('photo_urls', sa.JSON(), nullable=True))
    op.add_column('journals', sa.Column('voice_memo_urls', sa.JSON(), nullable=True))
    op.add_column('journals', sa.Column('voice_memo_durations', sa.JSON(), nullable=True))
    op.add_column('journals', sa.Column('pdf_urls', sa.JSON(), nullable=True))
    op.add_column('journals', sa.Column('pdf_names', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove the added columns
    op.drop_column('journals', 'pdf_names')
    op.drop_column('journals', 'pdf_urls')
    op.drop_column('journals', 'voice_memo_durations')
    op.drop_column('journals', 'voice_memo_urls')
    op.drop_column('journals', 'photo_urls')
    op.drop_column('journals', 'shared_with_coach')
    op.drop_column('journals', 'date')
    op.drop_column('journals', 'notes')
    op.drop_column('journals', 'quick_note')
    op.drop_column('journals', 'sleep')
    op.drop_column('journals', 'emotions')
    op.drop_column('journals', 'mood')
