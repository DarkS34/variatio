"""The two languages where a request sets them, and the fact that they are two.

`users.ui_language` is what a person reads; `workspaces.prompt_language` is what a model is
instructed in. Nothing here couples them, and the test that matters most is the one that
proves it: setting one must leave the other exactly where it was, or the whole reason for
having two columns disappears the first time somebody switches interface language.
"""

from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.responses import Response

from server.auth import passwords, rate_limit
from server.db import identity, repository
from server.db.models import Base
from server.routers.admin import InviteBody, create_invite
from server.routers.auth import AcceptBody, LanguageBody, accept_invite, change_language


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(identity, "now", datetime.now)
    monkeypatch.setattr(passwords, "hash_password", lambda password: "hashed")
    yield session
    session.close()


@pytest.fixture
def admin(db):
    return identity.create_user(
        db, username="admin", name="admin", password_hash="x", is_admin=True
    )


# The `accept` bucket is keyed by IP and by invitation, and the limiter outlives a test:
# every request below comes from the same fake address, so the run would throttle itself.
@pytest.fixture(autouse=True)
def forget_the_address():
    rate_limit.unlock("accept", "10.0.0.1")


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"host", b"localhost"), (b"origin", b"http://localhost")],
            "client": ("10.0.0.1", 1234),
            "scheme": "http",
            "server": ("localhost", 8000),
            "query_string": b"",
        }
    )


def _register(db, admin, username: str, language):
    link = create_invite(
        InviteBody(workspace=None, role="editor"), _request(), admin=admin, db=db
    )["link"]
    accept_invite(
        AcceptBody(
            token=link.split("token=")[1],
            username=username,
            name=username,
            password="una-contraseña-larga",
            evaluator_profile="teacher",
            ui_language=language,
        ),
        _request(),
        Response(),
        session=db,
    )
    return identity.get_user(db, username)


# REGISTRATION ---------------------------------------------------------------------------


def test_the_language_chosen_while_registering_is_the_accounts(db, admin):
    assert _register(db, admin, "ana", "en").ui_language == "en"


def test_a_browser_tag_is_accepted_and_folded(db, admin):
    # The form seeds itself from `navigator.language`, which is never a bare code.
    assert _register(db, admin, "bruno", "en-GB").ui_language == "en"


def test_registering_without_saying_is_allowed_and_lands_in_spanish(db, admin):
    # Unlike the evaluator profile, this one has a right answer to fall back on: NULL would
    # mean an account that reads no language, which is not a state anything can render.
    assert _register(db, admin, "carla", None).ui_language == "es"


def test_a_language_the_installation_does_not_speak_is_refused(db, admin):
    with pytest.raises(HTTPException) as refused:
        _register(db, admin, "dani", "fr")
    assert refused.value.status_code == 422
    assert "fr" in refused.value.detail
    assert identity.get_user(db, "dani") is None


# CHANGING IT AFTERWARDS ------------------------------------------------------------------


def test_an_account_changes_its_own(db, admin):
    user = _register(db, admin, "elena", "es")
    assert change_language(LanguageBody(language="en"), user=user, session=db) == {
        "ui_language": "en"
    }
    assert identity.get_user(db, "elena").ui_language == "en"


def test_changing_it_to_something_unknown_leaves_it_alone(db, admin):
    user = _register(db, admin, "fran", "es")
    with pytest.raises(HTTPException) as refused:
        change_language(LanguageBody(language="fr"), user=user, session=db)
    assert refused.value.status_code == 422
    assert identity.get_user(db, "fran").ui_language == "es"


# THE TWO AXES ----------------------------------------------------------------------------


def test_a_workspace_declares_its_own_prompt_language(db):
    assert repository.create_workspace(db, "aula", "Aula").prompt_language == "es"
    assert (
        repository.create_workspace(db, "class", "Class", prompt_language="en").prompt_language
        == "en"
    )


def test_the_interface_language_and_the_prompt_language_do_not_touch_each_other(db, admin):
    # The case the whole design exists for: somebody working in Spanish preparing an
    # instance whose prompts are English.
    user = _register(db, admin, "gema", "es")
    workspace = repository.create_workspace(db, "english", "English", prompt_language="en")

    identity.set_ui_language(db, user, "en")
    assert repository.get_workspace(db, "english").prompt_language == "en"

    identity.set_ui_language(db, user, "es")
    assert identity.get_user(db, "gema").ui_language == "es"
    assert workspace.prompt_language == "en"


# THE MIRROR ------------------------------------------------------------------------------


def test_importing_a_directory_brings_its_language_into_the_row(db, tmp_path):
    from server.db.instance_io import import_instance
    from variatio.core.workspace import Workspace as FsWorkspace
    from variatio.instance import locale

    ws = FsWorkspace(root=tmp_path / "ingles", slug="ingles")
    locale.set_prompt_language(ws, "en")

    summary = import_instance(db, ws, "ingles", "Inglés")
    assert summary["prompt_language"] == "en"
    assert repository.get_workspace(db, "ingles").prompt_language == "en"


def test_exporting_writes_the_language_out_even_with_nothing_built(db, tmp_path):
    from server.db.instance_io import export_instance
    from variatio.core.workspace import Workspace as FsWorkspace
    from variatio.instance import locale

    repository.create_workspace(db, "salida", "Salida", prompt_language="en")
    ws = FsWorkspace(root=tmp_path / "salida", slug="salida")

    # Unconditional, unlike an artifact: for an English instance an absent file is not a
    # missing fact, it is the wrong one — it reads as Spanish.
    export_instance(db, "salida", ws)
    assert locale.prompt_language(ws) == "en"


def test_the_language_survives_a_round_trip(db, tmp_path):
    from server.db.instance_io import export_instance, import_instance
    from variatio.core.workspace import Workspace as FsWorkspace
    from variatio.instance import locale

    source = FsWorkspace(root=tmp_path / "a", slug="ida")
    locale.set_prompt_language(source, "en")
    import_instance(db, source, "ida", "Ida")

    destination = FsWorkspace(root=tmp_path / "b", slug="ida")
    export_instance(db, "ida", destination)
    assert locale.prompt_language(destination) == "en"
