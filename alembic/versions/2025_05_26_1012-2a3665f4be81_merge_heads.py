"""Merge heads

Revision ID: 2a3665f4be81
Revises: e9776e9576bd, add_journal_enhanced_fields
Create Date: 2025-05-26 10:12:34.878123

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2a3665f4be81"
down_revision: Union[str, None] = ("e9776e9576bd", "add_journal_enhanced_fields")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
