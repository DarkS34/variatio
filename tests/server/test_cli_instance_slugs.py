from types import SimpleNamespace

import pytest

from server.cli import instances
from variatio.core import paths

# Both arguments of each command become a filesystem path: `paths.workspace('../etc')`
# resolves outside `workspaces/` and `paths.workspace('/etc')` resolves to `/etc`.
ESCAPES = ["../etc", "/etc", "..", "../../root", "a/b", "aula/../../etc", ".", "~"]
MALFORMED = ["", "ab", "A", "-aula", "aula-", "aula_1", "aula 1", "x" * 65]


def _import(slug: str, from_workspace: str | None = None):
    return instances.import_instance(
        SimpleNamespace(slug=slug, from_workspace=from_workspace, name=None)
    )


def _export(slug: str, to_workspace: str | None = None):
    return instances.export_instance(SimpleNamespace(slug=slug, to_workspace=to_workspace))


def test_the_escapes_would_leave_the_workspaces_directory():
    assert not paths.workspace("../etc").root.resolve().is_relative_to(paths.WORKSPACES_DIR)
    assert str(paths.workspace("/etc").root) == "/etc"


@pytest.mark.parametrize("slug", ESCAPES + MALFORMED)
def test_import_refuses_a_slug_that_is_not_one(slug, capsys):
    assert _import(slug) == 1
    assert "no vale como workspace" in capsys.readouterr().out


@pytest.mark.parametrize("slug", ESCAPES)
def test_import_refuses_a_source_workspace_that_is_not_one(slug, capsys):
    assert _import("aula", slug) == 1
    assert slug in capsys.readouterr().out


@pytest.mark.parametrize("slug", ESCAPES + MALFORMED)
def test_export_refuses_a_slug_that_is_not_one(slug, capsys):
    assert _export(slug) == 1
    assert "no vale como workspace" in capsys.readouterr().out


@pytest.mark.parametrize("slug", ESCAPES)
def test_export_refuses_a_destination_workspace_that_is_not_one(slug, capsys):
    assert _export("aula", slug) == 1
    assert slug in capsys.readouterr().out


# The refusal must not reach the database, or the row every other defect keys on is
# already written by the time anybody reads the message.
def test_a_refused_slug_never_opens_a_session(monkeypatch):
    def explode():
        raise AssertionError("no debería abrirse una sesión")

    monkeypatch.setattr("server.db.session_scope", explode)
    assert _import("../etc") == 1
    assert _export("../etc") == 1


def test_a_well_formed_slug_gets_past_the_check(monkeypatch):
    seen = {}

    class _Session:
        def __enter__(self):
            return object()

        def __exit__(self, *exc):
            return False

    def _load(session, ws, slug, name):
        seen["import"] = {"root": ws.root, "slug": slug}
        return {
            "workspace": slug,
            "workspace_id": 1,
            "artifacts": [],
            "approvals": 0,
            "raw_documents": 0,
        }

    monkeypatch.setattr("server.db.session_scope", lambda: _Session())
    monkeypatch.setattr("server.db.instance_io.import_instance", _load)

    assert _import("cs0-examenes") == 0
    assert seen["import"]["slug"] == "cs0-examenes"
    assert seen["import"]["root"] == paths.WORKSPACES_DIR / "cs0-examenes"
