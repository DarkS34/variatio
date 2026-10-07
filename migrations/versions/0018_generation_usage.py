"""a student's exercises per day, for the daily limit

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The exercises an account asked for per day, for a student's daily limit
    # (`generation.student_daily_items`), counted across every subject because the queue it
    # protects is the installation's. The shape of `tutor_usage`, and a table for its reason:
    # a count of the exercise files resets when their author deletes them.
    op.create_table(
        "generation_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("items", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "day", name="uq_generation_usage_day"),
    )
    op.create_index("ix_generation_usage_user_id", "generation_usage", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_generation_usage_user_id", table_name="generation_usage")
    op.drop_table("generation_usage")
