"""the free chat: a subject's switch for its students, and its own daily count

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The free chat is a subject's to open to its students, as generating and the tutor are,
    # and CLOSED by default (the user's decision, 2026-10-14): a teacher opens it.
    op.add_column(
        "workspaces",
        sa.Column("student_chat", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    # The daily count of the tutor serves the chat too: one row per account, day and function.
    # The rows already there are the tutor's.
    op.add_column(
        "tutor_usage",
        sa.Column("feature", sa.String(length=16), server_default="tutor", nullable=False),
    )
    with op.batch_alter_table("tutor_usage") as batch:
        batch.drop_constraint("uq_tutor_usage_day", type_="unique")
        batch.create_unique_constraint("uq_tutor_usage_day", ["user_id", "day", "feature"])


def downgrade() -> None:
    op.execute("DELETE FROM tutor_usage WHERE feature <> 'tutor'")
    with op.batch_alter_table("tutor_usage") as batch:
        batch.drop_constraint("uq_tutor_usage_day", type_="unique")
        batch.create_unique_constraint("uq_tutor_usage_day", ["user_id", "day"])
    op.drop_column("tutor_usage", "feature")
    op.drop_column("workspaces", "student_chat")
