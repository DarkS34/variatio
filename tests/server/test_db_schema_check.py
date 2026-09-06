"""A database that answers is not a database at the revision this code expects.

The state these pin shipped and was found the hard way: the installation ran at "0009"
while the code was written against "0010", so every request that loaded a `generations`
row asked for a column that did not exist — and what a person saw was a 500 on "borrar
workspace", a button that has nothing to do with which model wrote a variant. Nothing
refused to start and nothing said the word "migración".
"""

import pytest
from sqlalchemy import text

from server.db import schema, session

HEAD = next(iter(schema.head_revisions()))
BEHIND = "0009"


def _stamp(revision: str | None) -> None:
    """Leave the database at one revision, exactly as `alembic upgrade` does."""
    with session.engine().begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        if revision is None:
            return
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": revision},
        )


def test_the_migrations_declare_exactly_one_head():
    assert len(schema.head_revisions()) == 1


def test_a_schema_at_head_says_nothing():
    _stamp(HEAD)
    assert schema.mismatch() is None
    assert schema.applied_revisions() == {HEAD}


def test_a_database_that_never_migrated_is_told_which_command_to_run():
    _stamp(None)
    message = schema.mismatch()

    assert message is not None
    assert "alembic_version" in message
    assert schema.MIGRATE in message


def test_a_schema_behind_the_code_names_BOTH_revisions_and_the_command():
    _stamp(BEHIND)
    message = schema.mismatch()

    assert message is not None
    assert BEHIND in message and HEAD in message
    assert schema.MIGRATE in message


# Upgrading cannot fix a database that is AHEAD of the checkout, so saying "aplica las
# migraciones" there sends somebody to a command that will report nothing to do.
def test_a_revision_the_code_does_not_know_is_not_reported_as_a_pending_migration():
    _stamp("9999")
    message = schema.mismatch()

    assert message is not None
    assert "9999" in message
    assert schema.MIGRATE not in message


def test_serve_refuses_before_uvicorn_when_the_schema_is_behind(tmp_path, monkeypatch, capsys):
    import uvicorn

    from server.cli import serve as serve_mod

    _stamp(BEHIND)
    monkeypatch.setattr(serve_mod, "serve_lock_path", lambda: tmp_path / ".serve.lock")
    monkeypatch.setattr(
        uvicorn, "run", lambda *a, **k: pytest.fail("sirvió con el esquema desactualizado")
    )

    assert serve_mod.serve(None) == 1
    assert schema.MIGRATE in capsys.readouterr().out
