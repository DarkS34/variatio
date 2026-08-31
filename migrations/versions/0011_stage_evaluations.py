"""what a person answered about one build of one artifact

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

Json = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    # The blind comparison measured the variants and nothing measured the chain that makes
    # them: a workspace could be prepared end to end without recording whether its profile,
    # its graph or its bank were any good. The questions are asked on each stage's own
    # screen, right after the build, and land here.
    #
    # `artifact_hash` is what makes a row a measurement: it names the build that was on
    # screen. The unique constraint is over (workspace, user, artifact, hash), so
    # re-answering the same build replaces the answer while a REBUILD starts a new row —
    # «salió mal» and «lo rehíce y salió bien» are two data, not an edit of one.
    op.create_table(
        "stage_evaluations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("artifact", sa.String(length=32), nullable=False),
        sa.Column("artifact_hash", sa.String(length=64), nullable=True),
        sa.Column("job_id", sa.String(length=32), nullable=True),
        sa.Column("instrument", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("answers", Json, nullable=False, server_default="{}"),
        sa.Column("overall", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("opened_at", sa.Float(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        # SET NULL and not CASCADE, like `generations.user_id` and
        # `evaluation_sessions.user_id`: deleting an account must not delete the
        # measurements the study counted.
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "user_id",
            "artifact",
            "artifact_hash",
            name="uq_stage_evaluation_build",
        ),
    )
    op.create_index(
        "ix_stage_evaluations_workspace_id", "stage_evaluations", ["workspace_id"], unique=False
    )
    op.create_index("ix_stage_evaluations_user_id", "stage_evaluations", ["user_id"], unique=False)
    op.create_index("ix_stage_evaluations_artifact", "stage_evaluations", ["artifact"], unique=False)
    op.create_index("ix_stage_evaluations_overall", "stage_evaluations", ["overall"], unique=False)
    op.create_index(
        "ix_stage_evaluation_recent", "stage_evaluations", ["workspace_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_stage_evaluation_recent", table_name="stage_evaluations")
    op.drop_index("ix_stage_evaluations_overall", table_name="stage_evaluations")
    op.drop_index("ix_stage_evaluations_artifact", table_name="stage_evaluations")
    op.drop_index("ix_stage_evaluations_user_id", table_name="stage_evaluations")
    op.drop_index("ix_stage_evaluations_workspace_id", table_name="stage_evaluations")
    op.drop_table("stage_evaluations")
