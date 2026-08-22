"""the checks a generated variant was run through, beside the variant

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

Json = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("generations", sa.Column("checks", Json, nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "checks")
