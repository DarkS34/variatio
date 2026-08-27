"""Deleting the instance somebody is inside moves them, it does not strand them.

`users.active_workspace_id` is a preference and never an authorisation, so a stale one
costs a 403 rather than a read of somebody else's instance — but a pointer at a row that no
longer exists costs something worse than that: the tab keeps asking for a slug the API
answers 404 for, and the switcher has nothing to offer instead.

The criterion is not a new one. It is what `current_workspace_for` already applies once the
last choice is gone: the first workspace the account belongs to, and nothing when it
belongs to none — which is a normal account and a state the panel draws.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import settings as server_settings
from server.auth import deps as auth_deps
from server.db import identity, repository
from server.db.models import Base, EDITOR
from server.routers.admin import delete_workspace


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    # The tree is a separate decision and has its own test; what is under examination here
    # is which row the account points at afterwards.
    monkeypatch.setattr(server_settings, "destroy", lambda ws: False)
    yield session
    session.close()


def _workspace(db, slug: str):
    return repository.ensure_workspace(db, slug, slug.capitalize())


def _account(db, username: str, workspaces: list, active=None):
    user = identity.create_user(db, username=username, name=username, password_hash="x")
    for workspace in workspaces:
        identity.grant(db, workspace.id, user.id, EDITOR)
    user.active_workspace_id = (active or workspaces[0]).id if workspaces or active else None
    db.flush()
    return user


def test_deleting_the_active_workspace_lands_the_account_on_its_next_one(db):
    aula = _workspace(db, "aula")
    taller = _workspace(db, "taller")
    ana = _account(db, "ana", [aula, taller], active=taller)

    result = delete_workspace("taller", db)

    assert result["deleted"] == "taller"
    assert result["rehomed"] == {"ana": "aula"}
    assert ana.active_workspace_id == aula.id
    assert auth_deps.current_workspace_for(db, ana).slug == "aula"


def test_an_account_left_with_no_membership_lands_nowhere(db):
    aula = _workspace(db, "aula")
    _workspace(db, "taller")
    solo = _account(db, "solo", [aula])

    delete_workspace("aula", db)

    assert solo.active_workspace_id is None
    assert auth_deps.current_workspace_for(db, solo) is None


def test_only_the_accounts_that_were_inside_it_are_moved(db):
    aula = _workspace(db, "aula")
    taller = _workspace(db, "taller")
    dentro = _account(db, "dentro", [aula, taller], active=taller)
    fuera = _account(db, "fuera", [aula, taller], active=aula)

    result = delete_workspace("taller", db)

    assert set(result["rehomed"]) == {"dentro"}
    assert dentro.active_workspace_id == aula.id
    assert fuera.active_workspace_id == aula.id


# An administrator gets in anywhere, but «where do I land» is still their own memberships:
# dropping them into the first workspace of the installation is entering somebody else's
# instance without having asked, and that step was removed on purpose.
def test_an_administrator_with_no_membership_lands_nowhere_either(db):
    aula = _workspace(db, "aula")
    taller = _workspace(db, "taller")
    jefa = identity.create_user(db, username="jefa", name="jefa", password_hash="x")
    jefa.is_admin = True
    jefa.active_workspace_id = taller.id
    db.flush()

    delete_workspace("taller", db)

    assert jefa.active_workspace_id is None
    assert auth_deps.current_workspace_for(db, jefa) is None
    assert repository.get_workspace(db, "aula") is aula


def test_the_last_workspace_of_the_installation_is_still_refused(db):
    _workspace(db, "aula")
    with pytest.raises(Exception, match="único workspace"):
        delete_workspace("aula", db)
