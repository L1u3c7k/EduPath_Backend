"""Add question evaluation and attempt tracking columns.

Revision ID: 7f41c2a9d6e0
Revises: 0eb31f9c328d
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f41c2a9d6e0"
down_revision: Union[str, Sequence[str], None] = "0eb31f9c328d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "questions",
        "user_answer",
        existing_type=sa.String(),
        nullable=True,
    )
    op.add_column(
        "questions",
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "questions",
        sa.Column("ai_feedback", sa.String(), nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column("attempts_used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("questions", "is_correct", server_default=None)
    op.alter_column("questions", "attempts_used", server_default=None)


def downgrade() -> None:
    op.drop_column("questions", "attempts_used")
    op.drop_column("questions", "ai_feedback")
    op.drop_column("questions", "is_correct")
    op.alter_column(
        "questions",
        "user_answer",
        existing_type=sa.String(),
        nullable=False,
    )
