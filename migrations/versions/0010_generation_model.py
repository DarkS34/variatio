"""a variant records the model that wrote it

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Which model wrote the item stopped being a property of the installation on
    # 2026-08-29: the commission picks one of the models the configuration offers, and the
    # two on offer differ by minutes of waiting and by how much they deliberate. A row
    # already carries the rest of its commission for the same reason — a statement without
    # its parameters can be read but neither judged nor reproduced.
    #
    # NULLABLE and with no server default, deliberately: every row written before today
    # was produced by whatever `VARIANT_GENERATION_LLM` resolved to at the time, and
    # stamping them with today's answer would be inventing a measurement. NULL means
    # «nobody recorded it», which is the truth about those rows.
    op.add_column(
        "generations",
        sa.Column("model", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generations", "model")
