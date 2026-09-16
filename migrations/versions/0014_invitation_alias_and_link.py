"""an invitation keeps an internal alias and a sealed copy of its link

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The administrator names an invitation for themselves («Profesora de Enfermería») and
    # can read its link again after handing it over (2026-09-16, explicit user request).
    #
    # `label` is internal: the public preview a link opens never carries it.
    #
    # `token_sealed` is the token encrypted with a key that is NOT in the database
    # (`server/auth/links.py`), so a copy of this table still opens no door. Lookups keep
    # going through `token_hash`. Both are NULLABLE, and every row written before today
    # stays NULL: its token was shown once and never kept, so there is nothing to seal —
    # the panel says so, and pasting the old link back in is what fills it.
    op.add_column("invites", sa.Column("label", sa.String(length=120), nullable=True))
    op.add_column("invites", sa.Column("token_sealed", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("invites", "token_sealed")
    op.drop_column("invites", "label")
