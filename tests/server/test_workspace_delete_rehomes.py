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


# The route reports where the CALLER lands, so it needs one — every test here is about the
# accounts that were inside the instance, and this administrator is a member of none of them.
def _admin(db):
    user = identity.create_user(db, username="root", name="root", password_hash="x")
    user.is_admin = True
    db.flush()
    return user


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

    result = delete_workspace("taller", admin=_admin(db), db=db)

    assert result["deleted"] == "taller"
    assert result["rehomed"] == {"ana": "aula"}
    assert ana.active_workspace_id == aula.id
    assert auth_deps.current_workspace_for(db, ana).slug == "aula"


def test_an_account_left_with_no_membership_lands_nowhere(db):
    aula = _workspace(db, "aula")
    _workspace(db, "taller")
    solo = _account(db, "solo", [aula])

    delete_workspace("aula", admin=_admin(db), db=db)

    assert solo.active_workspace_id is None
    assert auth_deps.current_workspace_for(db, solo) is None


def test_only_the_accounts_that_were_inside_it_are_moved(db):
    aula = _workspace(db, "aula")
    taller = _workspace(db, "taller")
    dentro = _account(db, "dentro", [aula, taller], active=taller)
    fuera = _account(db, "fuera", [aula, taller], active=aula)

    result = delete_workspace("taller", admin=_admin(db), db=db)

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

    delete_workspace("taller", admin=_admin(db), db=db)

    assert jefa.active_workspace_id is None
    assert auth_deps.current_workspace_for(db, jefa) is None
    assert repository.get_workspace(db, "aula") is aula


# An installation holding ZERO workspaces is a normal state — the panel offers to create
# one — and `leave` already deletes the last workspace when its last member walks out. The
# guard that used to sit here refused the tidy way of doing what the untidy one allowed.
def test_the_last_workspace_of_the_installation_can_be_deleted(db):
    _workspace(db, "aula")
    delete_workspace("aula", admin=_admin(db), db=db)
    assert repository.list_workspaces(db) == []


# `rehomed` is about everybody; `landed` is the one entry the tab that made the request
# needs. Without it the browser blanks to «ningún espacio de trabajo» until `me` answers, which is
# the flicker this field exists to remove.
def test_the_answer_says_where_the_caller_itself_lands(db):
    aula = _workspace(db, "aula")
    taller = _workspace(db, "taller")
    root = _admin(db)
    identity.grant(db, aula.id, root.id, EDITOR)
    identity.grant(db, taller.id, root.id, EDITOR)
    root.active_workspace_id = taller.id
    db.flush()

    assert delete_workspace("taller", admin=root, db=db)["landed"] == "aula"


# Not being in the instance that goes and having nowhere left to go are two different
# states, and the panel draws both the same way: it stays where it is.
def test_a_caller_who_was_not_inside_it_lands_nowhere_new(db):
    _workspace(db, "aula")
    taller = _workspace(db, "taller")
    root = _admin(db)

    assert delete_workspace("taller", admin=root, db=db)["landed"] is None
