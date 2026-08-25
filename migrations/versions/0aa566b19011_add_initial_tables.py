"""Add initial tables

Revision ID: 0aa566b19011
Revises: 5fb251eb0e12
Create Date: 2026-08-25 15:00:07.692276

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0aa566b19011'
down_revision: Union[str, Sequence[str], None] = '5fb251eb0e12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
