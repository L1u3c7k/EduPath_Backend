"""add quiz completion fields and question number

Revision ID: afc5d813fcdb
Revises: 7f41c2a9d6e0
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "afc5d813fcdb"
down_revision: Union[str, None] = "7f41c2a9d6e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # quizzes
    # ---------------------------------------------------------

    op.add_column(
        "quizzes",
        sa.Column(
            "last_message_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    op.add_column(
        "quizzes",
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # ---------------------------------------------------------
    # questions
    # ---------------------------------------------------------

    # Existing questions already exist, so add nullable first.
    op.add_column(
        "questions",
        sa.Column(
            "question_number",
            sa.Integer(),
            nullable=True,
        ),
    )

    # Give existing questions their question numbers.
    op.execute(
        """
        WITH numbered AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY quiz_id
                    ORDER BY created_at, id
                ) AS number
            FROM questions
        )
        UPDATE questions
        SET question_number = numbered.number
        FROM numbered
        WHERE questions.id = numbered.id
        """
    )

    # Now that every existing row has a number,
    # make the column required.
    op.alter_column(
        "questions",
        "question_number",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column(
        "questions",
        "question_number",
    )

    op.drop_column(
        "quizzes",
        "completed_at",
    )

    op.drop_column(
        "quizzes",
        "last_message_id",
    )