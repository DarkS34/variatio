"""the interface language belongs to the account and the prompt language to the workspace

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Two languages that are NOT the same question. `users.ui_language` is what the person
    # reads; `workspaces.prompt_language` is what the model is instructed in. Both default to
    # «es» because that is what every account and every workspace written before today
    # factually is, so the migration changes nobody's behaviour.
    #
    # `workspaces.prompt_language` is a MIRROR of `instance/locale.json` and never the truth:
    # the pipeline runs from the command line with no database, so the file is what a build
    # reads. The column exists so the panel can list the instances without touching disk,
    # exactly as the artifact rows mirror the files beside them.
    op.add_column(
        "users",
        sa.Column("ui_language", sa.String(8), nullable=False, server_default="es"),
    )
    op.add_column(
        "workspaces",
        sa.Column("prompt_language", sa.String(8), nullable=False, server_default="es"),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "prompt_language")
    op.drop_column("users", "ui_language")
