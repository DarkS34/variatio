"""the evaluation and the tutor are switched per installation and per account

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

Json = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    # One branch carries the evaluation and the tutor from 2026-10-03, and the administrator
    # decides who each is for: nobody, every account, or a list (explicit user request).
    #
    # `feature_access` has no row to start with, and a function with no row is OFF: an
    # installation that upgrades loses both doors until its administrator opens them.
    op.create_table(
        "feature_access",
        sa.Column("feature", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=16), server_default="off", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("feature"),
    )
    op.create_table(
        "feature_grants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feature", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature", "user_id", name="uq_feature_grant"),
    )
    op.create_index("ix_feature_grants_feature", "feature_grants", ["feature"])
    op.create_index("ix_feature_grants_user_id", "feature_grants", ["user_id"])

    # What an invitation lists its holder for at registration. Every invitation minted before
    # today lists nothing.
    op.add_column("invites", sa.Column("features", Json, nullable=False, server_default="[]"))

    # The tutor's turns per account and day, for the installation's daily limit. A table and
    # not a count of the conversation files, which their author can delete.
    op.create_table(
        "tutor_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("turns", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "day", name="uq_tutor_usage_day"),
    )
    op.create_index("ix_tutor_usage_user_id", "tutor_usage", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_tutor_usage_user_id", table_name="tutor_usage")
    op.drop_table("tutor_usage")
    op.drop_column("invites", "features")
    op.drop_index("ix_feature_grants_user_id", table_name="feature_grants")
    op.drop_index("ix_feature_grants_feature", table_name="feature_grants")
    op.drop_table("feature_grants")
    op.drop_table("feature_access")
