"""add message hierarchy fields

Revision ID: 0cffaf6bc621
Revises: 332f2c41f1f7
Create Date: 2026-10-04 23:58:11.610110

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0cffaf6bc621"
down_revision: Union[str, Sequence[str], None] = "332f2c41f1f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column(
            "subject",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "messages",
        sa.Column(
            "chapter",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "messages",
        sa.Column(
            "topic",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "messages",
        sa.Column(
            "subtopic",
            sa.String(length=255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "messages",
        "subtopic",
    )

    op.drop_column(
        "messages",
        "topic",
    )

    op.drop_column(
        "messages",
        "chapter",
    )

    op.drop_column(
        "chats",
        "subject",
    )