"""a teacher's favourite exercises of a subject's bank

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The exercises of a bank a teacher marked with the star: a mark of one account in one
    # subject, so a row and not a file of the subject's (`tutor_usage`'s reason). The exercise
    # is named by its CONTENT (`item_key`, a fingerprint of its folded statement) and not by
    # its id, which a re-extraction renumbers.
    op.create_table(
        "bank_favourites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("item_key", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", "item_key", name="uq_bank_favourite"),
    )
    op.create_index("ix_bank_favourites_workspace_id", "bank_favourites", ["workspace_id"])
    op.create_index("ix_bank_favourites_user_id", "bank_favourites", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_bank_favourites_user_id", table_name="bank_favourites")
    op.drop_index("ix_bank_favourites_workspace_id", table_name="bank_favourites")
    op.drop_table("bank_favourites")
