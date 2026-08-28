"""Leaving a workspace, which is only sometimes the same act as deleting it.

`DELETE /api/workspaces/{slug}` is the owner disposing of a shared instance. This is a
person disposing of their own access, and the two collapse into one exactly when the person
leaving is the last one linked to it: with the seat empty there is nobody left for the
workspace to belong to.

What the tests pin is the arithmetic of that «exactly when», the two states the register
calls normal — an installation with no workspaces, an account belonging to none — and the
one thing that must NOT happen either way: the directory tree survives, because it holds
documents the person uploaded and a web request does not silently delete those.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi import HTTPException

from server.db import identity, repository
from server.db.models import Base, EDITOR, OWNER
from server.routers.workspaces import leave


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def _workspace(db, slug: str):
    return repository.ensure_workspace(db, slug, slug.capitalize())


def _account(db, username: str, grants: list, active=None, admin: bool = False):
    user = identity.create_user(db, username=username, name=username, password_hash="x")
    user.is_admin = admin
    for workspace, role in grants:
        identity.grant(db, workspace.id, user.id, role)
    if active is not None:
        user.active_workspace_id = active.id
    db.flush()
    return user


def test_the_last_member_out_takes_the_workspace_with_them(db):
    aula = _workspace(db, "aula")
    ana = _account(db, "ana", [(aula, OWNER)], active=aula)

    result = leave("aula", user=ana, db=db)

    assert result["deleted"] is True
    assert result["members_left"] == 0
    assert repository.get_workspace(db, "aula") is None
    # An account that belongs to none is a normal account, so the pointer is cleared rather
    # than left aiming at a row that no longer exists.
    assert ana.active_workspace_id is None


def test_leaving_a_shared_workspace_removes_only_that_seat(db):
    aula = _workspace(db, "aula")
    ana = _account(db, "ana", [(aula, OWNER)], active=aula)
    bruno = _account(db, "bruno", [(aula, EDITOR)], active=aula)

    result = leave("aula", user=bruno, db=db)

    assert result["deleted"] is False
    assert result["members_left"] == 1
    assert repository.get_workspace(db, "aula") is not None
    assert identity.membership(db, aula.id, bruno.id) is None
    assert identity.membership(db, aula.id, ana.id) is not None
    assert bruno.active_workspace_id is None
    assert ana.active_workspace_id == aula.id


def test_the_last_member_takes_it_even_when_they_do_not_own_it(db):
    # The case exists: an owner's account was deleted and `memberships` went with it.
    # Refusing here would strand an instance nobody but an administrator could reopen.
    aula = _workspace(db, "aula")
    bruno = _account(db, "bruno", [(aula, EDITOR)], active=aula)

    result = leave("aula", user=bruno, db=db)

    assert result["deleted"] is True
    assert repository.get_workspace(db, "aula") is None


def test_an_administrator_with_no_seat_has_nothing_to_leave(db):
    # They reach every instance through the bypass and usually hold no row at all. Letting
    # this route delete on that basis would be a different act wearing this one's name.
    aula = _workspace(db, "aula")
    _account(db, "ana", [(aula, OWNER)], active=aula)
    root = _account(db, "root", [], admin=True)

    with pytest.raises(HTTPException) as raised:
        leave("aula", user=root, db=db)

    assert raised.value.status_code == 409
    assert repository.get_workspace(db, "aula") is not None


def test_leaving_the_installation_s_only_workspace_is_allowed(db):
    # `remove` refuses this and predates the decision that an installation may hold zero
    # workspaces. Refusing here would make «no workspace» reachable only by an administrator.
    aula = _workspace(db, "aula")
    ana = _account(db, "ana", [(aula, OWNER)], active=aula)

    assert leave("aula", user=ana, db=db)["deleted"] is True
    assert repository.list_workspaces(db) == []


def test_a_workspace_that_does_not_exist_is_a_404(db):
    ana = _account(db, "ana", [])

    with pytest.raises(HTTPException) as raised:
        leave("fantasma", user=ana, db=db)

    assert raised.value.status_code == 404
