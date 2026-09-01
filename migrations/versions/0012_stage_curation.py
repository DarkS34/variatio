"""a stage verdict records whether whoever gave it had curated the artifact

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Curating — correcting by hand what the system wrote — stopped being required in order
    # to move down the chain. What that used to guarantee is recovered here as a variable
    # instead of being lost: how somebody who corrected the artifact rates it, against how
    # somebody who left it exactly as it came out rates it. Pooled in one average the two
    # populations cancel, and neither can be read afterwards.
    #
    # BOOLEAN AND NULLABLE, which is three states rather than two. Every row written before
    # today was answered by somebody who may or may not have curated first, and nothing
    # recorded which: stamping them `False` would assert a measurement nobody took, exactly
    # as `generations.model` refused to stamp older rows with the day's default. NULL means
    # «nadie lo dijo», `False` is somebody saying they did not.
    op.add_column(
        "stage_evaluations",
        sa.Column("curated", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stage_evaluations", "curated")
