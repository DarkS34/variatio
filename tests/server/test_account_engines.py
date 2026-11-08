"""Each account runs on its engine, and the process holds the engines its accounts run on."""

import pytest
from fastapi import HTTPException

from server.admin.routes import accounts as admin_accounts
from server.auth import engines as auth_engines
from server.auth import queries
from server.core import process
from server.db import session as db_session
from server.db import session_scope
from server.db.models import Base
from server.jobs.bus import EventBus
from server.jobs.runner import JobRunner
from variatio import config, inference
from variatio.inference.engines import EngineSet


@pytest.fixture
def installation(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_HOST", "http://localhost:13434")
    monkeypatch.setattr(config, "INFERENCE_ENGINE", "ollama")
    monkeypatch.setattr(config, "ENGINES_AVAILABLE", ["cerebras+ollama", "nada"])
    engines = EngineSet()
    monkeypatch.setattr(process, "engines", engines)
    Base.metadata.create_all(db_session.engine())
    with session_scope() as db:
        for name in ("ana", "luis"):
            queries.create_user(db, username=name, name=name, password_hash="x")
    yield engines
    engines.close_all()


def _user(db, username):
    return queries.get_user(db, username)


def test_the_default_is_offered_first_and_an_unknown_name_is_not(installation):
    assert auth_engines.offered() == ["ollama", "cerebras+ollama"]


def test_an_account_with_no_engine_runs_on_the_default(installation):
    with session_scope() as db:
        assert auth_engines.name_for(_user(db, "ana")) == "ollama"
        assert auth_engines.accounts_per_engine(db) == {"ollama": 2}


def test_sync_builds_only_the_engines_some_account_runs_on(installation):
    auth_engines.sync()
    assert installation.names() == ["ollama"]


def test_moving_every_account_closes_the_engine_they_left(installation):
    auth_engines.sync()
    with session_scope() as db:
        for name in ("ana", "luis"):
            user = _user(db, name)
            admin_accounts.set_engine(user.id, admin_accounts.EngineBody(engine="cerebras+ollama"), db)
    assert installation.names() == ["cerebras+ollama"]


def test_an_engine_the_installation_does_not_offer_is_refused(installation):
    with session_scope() as db:
        user = _user(db, "ana")
        with pytest.raises(HTTPException) as refused:
            admin_accounts.set_engine(user.id, admin_accounts.EngineBody(engine="vllm"), db)
    assert refused.value.status_code == 422


def test_the_panel_counts_the_accounts_of_each_engine_and_builds_none(installation):
    with session_scope() as db:
        user = _user(db, "ana")
        admin_accounts.set_engine(user.id, admin_accounts.EngineBody(engine="cerebras+ollama"), db)
        installation.close_all()
        listing = admin_accounts.engines(db)
    assert listing["default"] == "ollama"
    assert listing["engines"] == [
        {"name": "ollama", "users": 1, "live": False},
        {"name": "cerebras+ollama", "users": 1, "live": False},
    ]
    assert installation.names() == []


def test_a_job_runs_on_the_engine_it_was_accepted_on(installation):
    seen = []
    runner = JobRunner(EventBus(), {"pensar": lambda job, control: seen.append(1)}, installation)
    with inference.using(installation.get("cerebras+ollama")):
        job = runner.submit("pensar", workspace="ws")
    assert job.engine == "cerebras+ollama"
    with runner._on_its_engine(job):
        assert inference.engine_name() == "cerebras+ollama"
        installation.keep({"ollama"})
        assert installation.existing("cerebras+ollama") is not None
    assert installation.existing("cerebras+ollama") is None


def test_a_request_runs_on_the_engine_of_the_account_behind_its_cookie(installation, monkeypatch):
    from server.auth.tokens import digest

    with session_scope() as db:
        user = _user(db, "ana")
        admin_accounts.set_engine(user.id, admin_accounts.EngineBody(engine="cerebras+ollama"), db)
    # The session lookup is `deps.resolve`'s and is tested there; SQLite drops the timezone
    # its expiry is compared with, so the lookup is answered here by the account itself.
    def live_session(db, token_hash):
        return (None, _user(db, "ana")) if token_hash == digest("galleta") else None

    monkeypatch.setattr(auth_engines.queries, "live_session", live_session)
    assert auth_engines._engine_for_token("galleta").name == "cerebras+ollama"
    assert auth_engines._engine_for_token("otra").name == "ollama"
    assert auth_engines._engine_for_token(None).name == "ollama"
