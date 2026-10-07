"""an optional function opened to whole subjects, not only to listed accounts

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The tutor for a subject (2026-10-06, the class plan's phase 15): beside the accounts on a
    # function's list, the subjects on it — everybody in one of them uses the function there.
    # No row to start with, so nothing opens to anybody new on upgrade.
    op.create_table(
        "feature_subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feature", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature", "workspace_id", name="uq_feature_subject"),
    )
    op.create_index("ix_feature_subjects_feature", "feature_subjects", ["feature"])
    op.create_index("ix_feature_subjects_workspace_id", "feature_subjects", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_feature_subjects_workspace_id", table_name="feature_subjects")
    op.drop_index("ix_feature_subjects_feature", table_name="feature_subjects")
    op.drop_table("feature_subjects")
