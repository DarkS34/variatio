"""where a saved variant went when it was promoted into the exemplars bank

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generations", sa.Column("promoted_item_id", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "promoted_item_id")
