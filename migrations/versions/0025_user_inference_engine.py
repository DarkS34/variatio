"""the inference engine each account runs on

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NULL is the installation's default engine (`engine.name`), so every account there is
    # keeps the engine it ran on.
    op.add_column("users", sa.Column("inference_engine", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "inference_engine")
