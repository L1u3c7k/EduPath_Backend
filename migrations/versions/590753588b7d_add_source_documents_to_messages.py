"""add source documents to messages

Revision ID: 590753588b7d
Revises: 50d23f40f294
Create Date: 2026-10-08 20:03:48.910912

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "590753588b7d"
down_revision: Union[str, Sequence[str], None] = "50d23f40f294"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "messages",
        sa.Column(
            "source_documents",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        "messages",
        "source_documents",
    )