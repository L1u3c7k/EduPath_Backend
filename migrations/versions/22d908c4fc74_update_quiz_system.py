"""update quiz system

Revision ID: 22d908c4fc74
Revises: cae64c316602
Create Date: 2026-10-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "22d908c4fc74"
down_revision: Union[str, Sequence[str], None] = "cae64c316602"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # --------------------------------------------------
    # quizzes
    # --------------------------------------------------

    op.add_column(
        "quizzes",
        sa.Column(
            "current_question",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )

    op.add_column(
        "quizzes",
        sa.Column(
            "last_message_id",
            sa.Integer(),
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

    # --------------------------------------------------
    # messages
    # --------------------------------------------------

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

    # --------------------------------------------------
    # questions
    # --------------------------------------------------

    op.add_column(
        "questions",
        sa.Column(
            "question_number",
            sa.Integer(),
            nullable=True,
        ),
    )

    # Number existing questions within each quiz.
    op.execute(
        sa.text(
            """
            UPDATE questions AS q
            SET question_number = numbered.question_number
            FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY quiz_id
                        ORDER BY id
                    ) AS question_number
                FROM questions
            ) AS numbered
            WHERE q.id = numbered.id
            """
        )
    )

    op.alter_column(
        "questions",
        "question_number",
        nullable=False,
    )

    # Remove the old answer column.
    # Student answers are now stored in quiz_attempts.
    op.drop_column(
        "questions",
        "user_answer",
    )

    # --------------------------------------------------
    # quiz_attempts
    # --------------------------------------------------

    op.create_table(
        "quiz_attempts",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "question_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "attempt_number",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "user_answer",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "is_correct",
            sa.Boolean(),
            nullable=False,
        ),

        sa.Column(
            "feedback",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:

    # --------------------------------------------------
    # quiz_attempts
    # --------------------------------------------------

    op.drop_table("quiz_attempts")

    # --------------------------------------------------
    # questions
    # --------------------------------------------------

    # Restore the old user_answer column.
    op.add_column(
        "questions",
        sa.Column(
            "user_answer",
            sa.String(),
            nullable=False,
        ),
    )

    op.drop_column(
        "questions",
        "question_number",
    )

    # --------------------------------------------------
    # messages
    # --------------------------------------------------

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

    # --------------------------------------------------
    # quizzes
    # --------------------------------------------------

    op.drop_column(
        "quizzes",
        "completed_at",
    )

    op.drop_column(
        "quizzes",
        "last_message_id",
    )

    op.drop_column(
        "quizzes",
        "current_question",
    )