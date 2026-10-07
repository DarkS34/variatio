"""a subject has a class: the account's profile, memberships that pause, class links

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A teacher brings their class into a subject (2026-10-06, the user's plan for a class).
    #
    # The account's profile stops being an answer of whoever registers and becomes what the
    # invitation set: a teacher creates subjects, a student does not. Every account that
    # exists today could create subjects, so the ones nobody answered for become teachers and
    # nothing changes for them; the ones that said they study stay students. An administrator
    # is a teacher whatever it answered — `set_admin` keeps it so from now on.
    op.execute(
        "UPDATE users SET evaluator_profile = 'teacher' "
        "WHERE evaluator_profile IS NULL OR is_admin"
    )

    # What an invitation makes of its holder. A row with no value is a student's — the way a
    # forgotten field fails closed — while the invitations nobody has used yet were minted
    # under the old rule, which let every account create subjects: they stay teachers'.
    op.add_column(
        "invites",
        sa.Column("profile", sa.String(length=16), nullable=False, server_default="student"),
    )
    op.execute("UPDATE invites SET profile = 'teacher' WHERE used_at IS NULL")

    # How somebody entered a subject, who let them in, and whether a teacher has paused them.
    # Every membership that exists is active, and its origin is unknown (NULL).
    op.add_column("memberships", sa.Column("via", sa.String(length=16), nullable=True))
    op.add_column(
        "memberships",
        sa.Column(
            "invited_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "memberships", sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "memberships",
        sa.Column(
            "disabled_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # A link many students redeem: seats, an expiry and a pause. At most one live link per
    # subject is a rule of the code, not an index, so SQLite and Postgres say the same.
    op.create_table(
        "class_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_sealed", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("uses", sa.Integer(), server_default="0", nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_class_links_workspace_id", "class_links", ["workspace_id"])


def downgrade() -> None:
    # The profiles the upgrade wrote stay: nothing recorded which ones it changed.
    op.drop_index("ix_class_links_workspace_id", table_name="class_links")
    op.drop_table("class_links")
    op.drop_column("memberships", "disabled_by")
    op.drop_column("memberships", "disabled_at")
    op.drop_column("memberships", "invited_by")
    op.drop_column("memberships", "via")
    op.drop_column("invites", "profile")
