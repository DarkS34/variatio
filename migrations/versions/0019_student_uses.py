"""what a subject's students may use: generating exercises and the tutor

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Two switches a subject's teachers set for its students, «Clase → Qué usan los alumnos»
    # (2026-10-06): closed during an exam, say. Open by default, so nothing changes for a
    # subject until a teacher closes one. They bind students alone; teachers keep both.
    op.add_column(
        "workspaces",
        sa.Column("student_generate", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "workspaces",
        sa.Column("student_tutor", sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "student_tutor")
    op.drop_column("workspaces", "student_generate")
