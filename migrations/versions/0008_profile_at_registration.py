"""the evaluator profile is answered when registering, not carried by the invitation

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nothing to preserve: the column only ever held a pre-assignment for links that had not
    # been redeemed yet, and the accounts already created keep their own `users` column.
    op.drop_column("invites", "evaluator_profile")


def downgrade() -> None:
    op.add_column("invites", sa.Column("evaluator_profile", sa.String(16), nullable=True))
