"""`export-generations`: the rows of the retired `generations` table, written out as files.

Run once per installation, before `alembic upgrade head` takes the table away — migration
0015 refuses to drop it while a row has no file. Idempotent: a row whose file exists is
left alone, so running it twice writes nothing the second time.

The table is read by reflection, not through a model: the model is gone, and this has to
work against a database that still has the table and code that no longer knows it.
"""

from datetime import datetime, timezone


def export_generations(args) -> int:
    """Write every row of `generations` as `<workspace>/generations/user_<id>/<UTC>-db<id>.json`."""
    from sqlalchemy import MetaData, Table, inspect, select

    from .. import generations as store
    from ..db import session_scope
    from ..installation import workspace_for

    dry_run = bool(args.dry_run)
    with session_scope() as session:
        bind = session.get_bind()
        if not inspect(bind).has_table("generations"):
            print("La tabla `generations` ya no existe en esta base: no queda nada que exportar.")
            return 0
        meta = MetaData()
        table = Table("generations", meta, autoload_with=bind)
        workspaces = Table("workspaces", meta, autoload_with=bind)
        users = Table("users", meta, autoload_with=bind)
        rows = session.execute(
            select(
                table,
                workspaces.c.slug.label("workspace_slug"),
                users.c.username.label("author_username"),
                users.c.name.label("author_name"),
            )
            .join(workspaces, workspaces.c.id == table.c.workspace_id)
            .outerjoin(users, users.c.id == table.c.user_id)
            .order_by(table.c.id)
        ).mappings().all()

    if not rows:
        print("La tabla `generations` está vacía: no hay nada que exportar.")
        return 0

    tally: dict[str, dict[str, int]] = {}
    for row in rows:
        slug = row["workspace_slug"]
        ws = workspace_for(slug)
        counts = tally.setdefault(slug, {"written": 0, "present": 0, "orphaned": 0, "treeless": 0})
        if not ws.root.is_dir():
            counts["treeless"] += 1
        if row["user_id"] is None:
            counts["orphaned"] += 1
        if any(ws.generations_dir.glob(f"*/*-db{row['id']}.json")):
            counts["present"] += 1
            continue
        if not dry_run:
            store.write(ws, row["user_id"], legacy_record(row))
        counts["written"] += 1

    verb = "se escribirían" if dry_run else "escritos"
    for slug, counts in tally.items():
        line = f"{slug}: {counts['written']} {verb}, {counts['present']} ya estaban"
        if counts["orphaned"]:
            line += f", {counts['orphaned']} sin autor (en generations/{store.ORPHANED}/)"
        if counts["treeless"]:
            line += " — la asignatura no tenía árbol en disco"
        print(line)
    if dry_run:
        print("Simulación: no se ha escrito nada.")
    else:
        print("Hecho. Ya se puede aplicar la migración: uv run alembic upgrade head")
    return 0


def legacy_record(row) -> dict:
    """Turn one row into a format-0 record, null wherever the table never kept the fact.

    The row's `item_type`, `curriculum` and `model` are what RAN, so they go under
    `resolved`; its `concepts`, `fixed`, `instructions` and `think` are what was asked.
    The targets, closures, few-shot, ruling, prompt and artifact hashes were never stored,
    and are not reconstructed.
    """
    from .. import generations as store

    created = row["created_at"] or datetime.fromtimestamp(0, timezone.utc)
    return {
        "format": store.LEGACY_FORMAT,
        "id": f"{store.stamp(created)}-db{row['id']}",
        "legacy_id": row["id"],
        "created_at": store.iso(created),
        "workspace": row["workspace_slug"],
        "author": {
            "id": row["user_id"],
            "username": row["author_username"],
            "name": row["author_name"],
        },
        "job": {"id": row["job_id"], "index": None, "requested": None},
        "commission": {
            "concepts": list(row["concepts"] or []),
            "item_type": None,
            "fixed": dict(row["fixed"] or {}),
            "curriculum": None,
            "instructions": row["instructions"] or None,
            "think": bool(row["think"]),
            "model": None,
        },
        "resolved": {
            "targets": None,
            "item_type": row["item_type"] or None,
            "curriculum": list(row["curriculum"] or []),
            "assumed_known": None,
            "forbidden": None,
            "closure_rule": None,
            "model": row["model"] or None,
            "effort": None,
            "scenario": None,
            "ruling": None,
            "avoid": None,
            "few_shot": None,
            "engine": None,
            "lane": None,
            "prompt_language": None,
        },
        "inputs": None,
        "settings": None,
        "system_version": None,
        "prompt": None,
        "output": {
            "item": dict(row["item"] or {}),
            "thinking": row["thinking"],
            "checks": row["checks"],
            "retried": None,
        },
        "promoted_item_id": row["promoted_item_id"],
    }
