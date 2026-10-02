"""The rows of the retired `generations` table become files, and the table goes only after.

`export-generations` reads the table by reflection — its model is gone — writes each row as
`<UTC>-db<row id>.json` under its author, and is idempotent. Migration 0015 refuses to drop
the table while any row has no such file, so an upgrade run in the wrong order stops
instead of losing exercises.
"""

import importlib.util
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa

from server import generations as store
from server.cli.generations import export_generations
from server.db import Base, identity, repository, session
from variatio.core import paths

MIGRATION = Path(__file__).parents[2] / "migrations" / "versions" / "0015_generations_to_files.py"
CREATED = datetime(2026, 9, 12, 8, 30, tzinfo=timezone.utc)


def _legacy_table(meta: sa.MetaData) -> sa.Table:
    """The table as migration 0014 left it."""
    return sa.Table(
        "generations",
        meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("job_id", sa.String(32)),
        sa.Column("item_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("concepts", sa.JSON, nullable=False),
        sa.Column("curriculum", sa.JSON, nullable=False),
        sa.Column("fixed", sa.JSON, nullable=False),
        sa.Column("instructions", sa.Text),
        sa.Column("think", sa.Boolean, nullable=False),
        sa.Column("item", sa.JSON, nullable=False),
        sa.Column("thinking", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checks", sa.JSON),
        sa.Column("promoted_item_id", sa.String(32)),
        sa.Column("model", sa.String(128)),
    )


@pytest.fixture
def database(monkeypatch, tmp_path):
    """The isolated database at revision 0014: one workspace, one account, three rows."""
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    engine = session.engine()
    Base.metadata.create_all(engine)
    table = _legacy_table(sa.MetaData(schema=None))
    table.metadata.reflect(engine, only=["workspaces", "users"])
    table.create(engine)
    with session.session_scope() as db:
        workspace = repository.ensure_workspace(db, "aula")
        user = identity.create_user(db, username="ana", name="Ana", password_hash="x")
        db.flush()
        ids = (workspace.id, user.id)
    common = dict(
        workspace_id=ids[0],
        item_type="ejercicio",
        curriculum=[],
        fixed={},
        think=True,
        created_at=CREATED,
        instructions=None,
        thinking=None,
        checks=None,
        model=None,
        promoted_item_id=None,
    )
    with engine.begin() as connection:
        connection.execute(
            table.insert(),
            [
                dict(common, id=1, user_id=ids[1], job_id="abc", concepts=["Bucles"],
                     item={"enunciado": "uno"}, model="qwen", promoted_item_id="C007"),
                dict(common, id=2, user_id=ids[1], job_id="abc", concepts=[],
                     item={"enunciado": "dos"}, instructions="de cocina"),
                dict(common, id=3, user_id=None, job_id=None, concepts=[],
                     item={"enunciado": "huérfano"}),
            ],
        )
    return Namespace(engine=engine, user_id=ids[1], ws=paths.workspace("aula"))


def _export(dry_run: bool = False) -> int:
    return export_generations(Namespace(dry_run=dry_run))


def _migration():
    spec = importlib.util.spec_from_file_location("migration_0015", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_row_becomes_a_file_under_its_author(database, capsys):
    assert _export() == 0

    records, total = store.list_for(database.ws, database.user_id)
    assert total == 2
    by_text = {store.item_of(r)["enunciado"]: r for r in records}
    first = by_text["uno"]
    assert first["id"] == "20260912T083000Z-db1"
    assert first["format"] == store.LEGACY_FORMAT
    assert first["author"] == {"id": database.user_id, "username": "ana", "name": "Ana"}
    assert first["commission"]["concepts"] == ["Bucles"]
    assert first["resolved"]["model"] == "qwen"
    assert first["promoted_item_id"] == "C007"
    assert by_text["dos"]["commission"]["instructions"] == "de cocina"
    orphaned = list((database.ws.generations_dir / store.ORPHANED).glob("*-db3.json"))
    assert len(orphaned) == 1
    assert "aula: 3 escritos, 0 ya estaban, 1 sin autor" in capsys.readouterr().out


def test_running_it_twice_writes_nothing_the_second_time(database, capsys):
    _export()
    capsys.readouterr()
    before = {p: p.stat().st_mtime_ns for p in database.ws.generations_dir.rglob("*.json")}

    _export()

    after = {p: p.stat().st_mtime_ns for p in database.ws.generations_dir.rglob("*.json")}
    assert after == before
    assert "aula: 0 escritos, 3 ya estaban" in capsys.readouterr().out


def test_a_dry_run_writes_nothing(database, capsys):
    _export(dry_run=True)

    assert not database.ws.generations_dir.exists()
    assert "3 se escribirían" in capsys.readouterr().out


def test_the_migration_refuses_while_a_row_has_no_file(database):
    migration = _migration()
    with database.engine.connect() as connection:
        assert migration._unexported(connection) == [1, 2, 3]

    _export()

    with database.engine.connect() as connection:
        assert migration._unexported(connection) == []


def test_a_promoted_flag_on_a_file_survives_a_second_export(database):
    """The file is the truth once written: exporting again must not undo a later edit."""
    _export()
    [record] = [
        r
        for r in store.list_for(database.ws, database.user_id)[0]
        if store.item_of(r)["enunciado"] == "dos"
    ]
    store.mark_promoted(database.ws, database.user_id, record, "C099")

    _export()

    assert store.get(database.ws, database.user_id, record["id"])["promoted_item_id"] == "C099"


def test_without_the_table_there_is_nothing_to_export(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    Base.metadata.create_all(session.engine())

    assert _export() == 0
    assert "ya no existe" in capsys.readouterr().out
