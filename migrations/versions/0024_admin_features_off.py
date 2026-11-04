"""the functions an administrator switched off for their own account

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

Json = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    # An administrator uses every function but the ones they switch off here (D-245). Empty for
    # every account there is, so every administrator keeps all of them.
    op.add_column("users", sa.Column("features_off", Json, nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("users", "features_off")
