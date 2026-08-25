"""Rename columns across models

Revision ID: ecc9ebe069c9
Revises: 0aa566b19011
Create Date: 2026-08-25 15:14:12.938636

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ecc9ebe069c9'
down_revision: Union[str, Sequence[str], None] = '0aa566b19011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Renames 'content' to 'message' directly, preserving all existing row data
    op.alter_column('messages', 'content', new_column_name='message')


def downgrade() -> None:
    """Downgrade schema."""
    # Reverts 'message' back to 'content'
    op.alter_column('messages', 'message', new_column_name='content')