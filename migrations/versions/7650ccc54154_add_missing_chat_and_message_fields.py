"""add missing chat and message fields

Revision ID: 7650ccc54154
Revises: 0cffaf6bc621
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7650ccc54154"
down_revision: Union[str, Sequence[str], None] = "0cffaf6bc621"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column("subject", sa.String(length=255), nullable=True),
    )

    op.add_column(
        "messages",
        sa.Column("chapter", sa.String(length=255), nullable=True),
    )

    op.add_column(
        "messages",
        sa.Column("topic", sa.String(length=255), nullable=True),
    )

    op.add_column(
        "messages",
        sa.Column("subtopic", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "subtopic")
    op.drop_column("messages", "topic")
    op.drop_column("messages", "chapter")
    op.drop_column("chats", "subject")