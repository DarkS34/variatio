"""groups inside a subject's class, and the links that bring students into one

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A group of a subject's students, with which a teacher does what they do with the class:
    # open or close each tool (NULL = as the subject says), follow its own progress (NULL = the
    # subject's), invite into it and read its activity.
    op.create_table(
        "class_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("generate", sa.Boolean(), nullable=True),
        sa.Column("tutor", sa.Boolean(), nullable=True),
        sa.Column("chat", sa.Boolean(), nullable=True),
        sa.Column(
            "progress", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_class_group_name"),
    )
    op.create_index("ix_class_groups_workspace_id", "class_groups", ["workspace_id"])
    # Who is in each group: one membership in one group at most for now (the user's decision,
    # 2026-10-14). A table and not a column of `memberships`, so several groups is dropping the
    # unique constraint rather than moving data.
    op.create_table(
        "class_group_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["class_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("membership_id", name="uq_class_group_member"),
    )
    op.create_index("ix_class_group_members_group_id", "class_group_members", ["group_id"])
    # A class link and a personal invitation may bring a student into one group.
    op.add_column("class_links", sa.Column("group_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_class_links_group_id", "class_links", "class_groups", ["group_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_class_links_group_id", "class_links", ["group_id"])
    op.add_column("invites", sa.Column("group_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_invites_group_id", "invites", "class_groups", ["group_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_invites_group_id", "invites", type_="foreignkey")
    op.drop_column("invites", "group_id")
    op.drop_index("ix_class_links_group_id", table_name="class_links")
    op.drop_constraint("fk_class_links_group_id", "class_links", type_="foreignkey")
    op.drop_column("class_links", "group_id")
    op.drop_index("ix_class_group_members_group_id", table_name="class_group_members")
    op.drop_table("class_group_members")
    op.drop_index("ix_class_groups_workspace_id", table_name="class_groups")
    op.drop_table("class_groups")
