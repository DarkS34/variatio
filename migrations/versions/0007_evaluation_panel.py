"""evaluator profiles, shared evaluation sets and what a blind session records

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("evaluator_profile", sa.String(16), nullable=True))
    op.add_column("invites", sa.Column("evaluator_profile", sa.String(16), nullable=True))

    op.add_column("evaluation_sessions", sa.Column("set_id", sa.String(32), nullable=True))
    op.add_column("evaluation_sessions", sa.Column("assigned_by", sa.Integer(), nullable=True))
    op.add_column(
        "evaluation_sessions",
        sa.Column("triage", sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"), nullable=True),
    )
    op.add_column("evaluation_sessions", sa.Column("opened_at", sa.Float(), nullable=True))
    op.add_column("evaluation_sessions", sa.Column("declined_at", sa.Float(), nullable=True))

    op.create_foreign_key(
        "fk_evaluation_assigned_by",
        "evaluation_sessions",
        "users",
        ["assigned_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_evaluation_set", "evaluation_sessions", ["set_id"])

    # Every session already recorded is its own set of three items: nobody had been handed a
    # copy of anybody's, because until now there was no way to. Backfilling rather than
    # leaving NULL is what lets every later query treat `set_id` as always present.
    op.execute("UPDATE evaluation_sessions SET set_id = id WHERE set_id IS NULL")
    op.execute("UPDATE evaluation_sessions SET triage = '{}' WHERE triage IS NULL")


def downgrade() -> None:
    op.drop_index("ix_evaluation_set", table_name="evaluation_sessions")
    op.drop_constraint("fk_evaluation_assigned_by", "evaluation_sessions", type_="foreignkey")
    op.drop_column("evaluation_sessions", "declined_at")
    op.drop_column("evaluation_sessions", "opened_at")
    op.drop_column("evaluation_sessions", "triage")
    op.drop_column("evaluation_sessions", "assigned_by")
    op.drop_column("evaluation_sessions", "set_id")
    op.drop_column("invites", "evaluator_profile")
    op.drop_column("users", "evaluator_profile")
