"""the generated exercises move to one JSON file each inside the workspace

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

Json = sa.JSON().with_variant(JSONB(), "postgresql")

EXPORT_HINT = "uv run system export-generations"


def upgrade() -> None:
    # Every validated exercise is now `<workspace>/generations/user_<id>/<id>.json`
    # (`server/generations.py`), written with what the row never kept: the resolved
    # targets, both closures, the few-shot, the ruling, the prompt and the artifact hashes
    # (2026-10-02, explicit user request).
    #
    # The table goes, but never with a row in it that has no file: `export-generations`
    # writes each row as `<UTC>-db<row id>.json`, and a row without one stops the upgrade
    # here, naming the command, instead of being lost to an upgrade run in the wrong order.
    missing = _unexported(op.get_bind())
    if missing:
        raise RuntimeError(
            f"{len(missing)} ejercicio(s) de la tabla `generations` no tienen todavía su "
            f"fichero (ids {_sample(missing)}). Expórtalos antes con `{EXPORT_HINT}` y "
            f"vuelve a aplicar la migración."
        )
    op.drop_table("generations")


def downgrade() -> None:
    # The table as 0014 left it, EMPTY: the exercises stay in their files, which is where
    # the code of that revision does not look for them.
    op.create_table(
        "generations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.String(length=32), nullable=True),
        sa.Column("item_type", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("concepts", Json, nullable=False),
        sa.Column("curriculum", Json, nullable=False),
        sa.Column("fixed", Json, nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("think", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("item", Json, nullable=False),
        sa.Column("thinking", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("checks", Json, nullable=True),
        sa.Column("promoted_item_id", sa.String(32), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generations_workspace_id", "generations", ["workspace_id"])
    op.create_index("ix_generations_user_id", "generations", ["user_id"])
    op.create_index("ix_generations_job_id", "generations", ["job_id"])
    op.create_index("ix_generation_recent", "generations", ["workspace_id", "created_at"])
    op.create_index(
        "ix_generation_author", "generations", ["workspace_id", "user_id", "created_at"]
    )


def _unexported(bind) -> list[int]:
    """Return the ids of the rows no exported file answers for.

    The path is spelled out rather than read off `Workspace`: a migration is a snapshot,
    and it has to keep meaning what it meant when the property is renamed.
    """
    from variatio.core import paths

    rows = bind.execute(
        sa.text(
            "SELECT g.id, w.slug FROM generations g "
            "JOIN workspaces w ON w.id = g.workspace_id ORDER BY g.id"
        )
    ).all()
    return [
        row_id
        for row_id, slug in rows
        if not any((paths.WORKSPACES_DIR / slug / "generations").glob(f"*/*-db{row_id}.json"))
    ]


def _sample(ids: list[int]) -> str:
    """Name the first few ids, enough to look one up."""
    shown = ", ".join(str(i) for i in ids[:5])
    return shown + (", …" if len(ids) > 5 else "")
