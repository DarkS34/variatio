"""What the CLI says when the database answers, and when it does not answer at all."""

import pytest
from sqlalchemy.exc import DataError, IntegrityError, OperationalError, ProgrammingError

from server.cli.common import DB_HINT, guarded
from server.db import refusal


def _raising(exc):
    @guarded
    def run(_args) -> int:
        raise exc

    return run


def _dbapi(kind, message: str):
    """Build a SQLAlchemy error the way the driver does: statement, params, and `orig`."""
    return kind("INSERT INTO artifacts …", {"content": "…" * 5000}, Exception(message))


# Telling somebody to start a Postgres they already have running is how a corrupt artifact
# spent months looking like a connection problem: `import-instance` printed "no connection to
# the database" while the database was up and had just refused a NUL byte.
@pytest.mark.parametrize("kind", [DataError, IntegrityError, ProgrammingError])
def test_a_rejected_operation_is_not_reported_as_a_dead_database(kind, capsys):
    exc = _dbapi(kind, "unsupported Unicode escape sequence")
    assert _raising(exc)(None) == 1

    printed = capsys.readouterr().out
    assert "No hay conexión" not in printed
    assert DB_HINT not in printed
    assert "unsupported Unicode escape sequence" in printed
    assert kind.__name__ in printed


def test_an_unreachable_database_still_gets_the_two_commands(capsys, monkeypatch):
    monkeypatch.setattr(
        "server.db.database_url", lambda: "postgresql://u:p@localhost:5432/x", raising=False
    )
    exc = _dbapi(OperationalError, "connection refused")
    assert _raising(exc)(None) == 1

    printed = capsys.readouterr().out
    assert "No hay conexión" in printed
    assert DB_HINT in printed


# `str()` of a DBAPIError carries the whole statement and every bound parameter, which for
# an artifact is hundreds of kilobytes of JSON. What a person can act on is one line.
def test_the_refusal_is_one_line_and_not_the_whole_statement():
    exc = _dbapi(DataError, "\\u0000 cannot be converted to text\nDETAIL: …\nCONTEXT: …")
    line = refusal(exc)

    assert line == "\\u0000 cannot be converted to text"
    assert "INSERT INTO" not in line


def test_a_lookup_failure_still_prints_its_own_sentence(capsys):
    assert _raising(LookupError("No existe el workspace 'aula'."))(None) == 1
    assert "No existe el workspace 'aula'." in capsys.readouterr().out
