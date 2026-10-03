"""remove current question from quiz

Revision ID: 332f2c41f1f7
Revises: 22d908c4fc74
Create Date: 2026-10-03 12:12:21.807792

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '332f2c41f1f7'
down_revision: Union[str, Sequence[str], None] = '22d908c4fc74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.drop_column(
        "quizzes",
        "current_question"
    )


def downgrade():
    op.add_column(
        "quizzes",
        sa.Column(
            "current_question",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )