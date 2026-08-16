"""usernames as the login identifier, addresses demoted to optional

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-16
"""

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALLOWED = re.compile(r"[^a-z0-9._-]+")


# Every account that predates this migration was named by its address, so its username is
# derived from the local part rather than left for someone to fill in by hand: a NOT NULL
# column added to a populated table has to come with an answer for every row.
def _derive(address: str, taken: set[str]) -> str:
    stem = _ALLOWED.sub(".", (address or "").split("@")[0].lower()).strip("._-")
    stem = (stem or "cuenta")[:60]
    if len(stem) < 3:
        stem = f"{stem}.usuario"
    candidate, suffix = stem, 2
    while candidate in taken:
        candidate = f"{stem}{suffix}"
        suffix += 1
    taken.add(candidate)
    return candidate


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=64), nullable=True))

    bind = op.get_bind()
    taken: set[str] = set()
    for user_id, email in bind.execute(sa.text("SELECT id, email FROM users ORDER BY id")):
        bind.execute(
            sa.text("UPDATE users SET username = :name WHERE id = :id"),
            {"name": _derive(email, taken), "id": user_id},
        )

    op.alter_column("users", "username", existing_type=sa.String(length=64), nullable=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # An address is now a delivery detail, and an account may have none at all. The unique
    # index stays: Postgres allows any number of NULLs under one, so it keeps refusing two
    # accounts with the same address without requiring anybody to have one.
    op.alter_column("users", "email", existing_type=sa.String(length=320), nullable=True)

    # An invitation no longer binds an address, because binding one was the proof of
    # mailbox control that replaced a verification round — and there is no mailbox in the
    # loop any more. The link itself is the whole credential, handed over by whoever
    # issued it.
    op.drop_column("invites", "email")


def downgrade() -> None:
    op.add_column("invites", sa.Column("email", sa.String(length=320), nullable=True))
    # Going back needs every account to have an address again, and this migration cannot
    # invent one, so the rows that arrived without it get a placeholder in the reserved
    # `.invalid` domain rather than a value that could be mistaken for a real mailbox.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE users SET email = username || '@sin-correo.invalid' WHERE email IS NULL"
        )
    )
    op.alter_column("users", "email", existing_type=sa.String(length=320), nullable=False)
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
