"""a stage form goes with the account that answered it

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The name Postgres gave the constraint `0011` declared without one.
_FK = "stage_evaluations_user_id_fkey"


def upgrade() -> None:
    # `0011` made `user_id` SET NULL «like generations and evaluation_sessions», and the
    # analogy was wrong (2026-09-03, explicit user request). Those two are material a
    # course was built on and sessions the evaluation counted; a stage form is one person's
    # verdict on a build, and with nobody behind it the panel can neither filter it,
    # group it nor withdraw it — six such rows were found stranded in production after
    # an account was deleted, and had to be removed by hand. From here on the account
    # takes its forms with it, exactly as it takes its memberships and open sessions.
    #
    # Rows already orphaned are NOT swept here: the constraint change is the rule, and
    # the sweep is a decision about data somebody may want to read first.
    op.drop_constraint(_FK, "stage_evaluations", type_="foreignkey")
    op.create_foreign_key(
        _FK, "stage_evaluations", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint(_FK, "stage_evaluations", type_="foreignkey")
    op.create_foreign_key(
        _FK, "stage_evaluations", "users", ["user_id"], ["id"], ondelete="SET NULL"
    )
