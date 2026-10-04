"""merge migration branches

Revision ID: 50d23f40f294
Revises: 7650ccc54154, afc5d813fcdb
Create Date: 2026-10-05 00:07:17.635953

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50d23f40f294'
down_revision: Union[str, Sequence[str], None] = ('7650ccc54154', 'afc5d813fcdb')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
