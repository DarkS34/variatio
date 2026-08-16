"""generations, evaluation sessions and the account's active workspace

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The same variant the models declare: Postgres gets JSONB, anything else plain JSON, so
# the import/export logic stays exercisable against SQLite with no server running.
Json = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("users", sa.Column("active_workspace_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_active_workspace",
        "users",
        "workspaces",
        ["active_workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "generations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.String(length=32), nullable=True),
        sa.Column("item_type", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("concepts", Json, nullable=False),
        sa.Column("curriculum", Json, nullable=False),
        sa.Column("fixed", Json, nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("think", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("item", Json, nullable=False),
        sa.Column("thinking", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generations_workspace_id", "generations", ["workspace_id"])
    op.create_index("ix_generations_user_id", "generations", ["user_id"])
    op.create_index("ix_generations_job_id", "generations", ["job_id"])
    op.create_index("ix_generation_recent", "generations", ["workspace_id", "created_at"])
    op.create_index(
        "ix_generation_author", "generations", ["workspace_id", "user_id", "created_at"]
    )

    op.create_table(
        "evaluation_sessions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("item_type", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("concepts", Json, nullable=False),
        sa.Column("curriculum", Json, nullable=False),
        sa.Column("fixed", Json, nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("seed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("shuffle", Json, nullable=False),
        sa.Column("think", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("choice", sa.Integer(), nullable=True),
        sa.Column("choice_arm", sa.String(length=16), nullable=True),
        sa.Column("chosen_at", sa.Float(), nullable=True),
        sa.Column("evaluator_note", sa.Text(), nullable=True),
        sa.Column("rating", Json, nullable=True),
        sa.Column("arm_status", Json, nullable=False),
        sa.Column("arm_elapsed_ms", Json, nullable=False),
        sa.Column("trace", Json, nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_sessions_workspace_id", "evaluation_sessions", ["workspace_id"])
    op.create_index("ix_evaluation_sessions_user_id", "evaluation_sessions", ["user_id"])
    op.create_index("ix_evaluation_sessions_choice_arm", "evaluation_sessions", ["choice_arm"])
    op.create_index("ix_evaluation_recent", "evaluation_sessions", ["workspace_id", "created_at"])


def downgrade() -> None:
    op.drop_table("evaluation_sessions")
    op.drop_table("generations")
    op.drop_constraint("fk_users_active_workspace", "users", type_="foreignkey")
    op.drop_column("users", "active_workspace_id")
