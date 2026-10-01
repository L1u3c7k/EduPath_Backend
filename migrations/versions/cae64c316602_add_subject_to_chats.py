"""add subject to chats

Revision ID: cae64c316602
Revises: c19f6a8d2b44
Create Date: 2026-09-30 18:36:14.732693

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cae64c316602"
down_revision: Union[str, Sequence[str], None] = "c19f6a8d2b44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "chats",
        sa.Column(
            "subject",
            sa.String(length=255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        "chats",
        "subject",
    )
