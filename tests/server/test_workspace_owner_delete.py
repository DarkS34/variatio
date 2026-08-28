"""The owner disposing of their own instance, which had a route and no way to reach it.

`DELETE /api/workspaces/{slug}` was written, tested at the edges and never wired to a
button, so «borrar un workspace mío» was not something the application could do. What the
tests here pin is the behaviour that had to change for it to be worth wiring: the last
workspace of the installation is deletable, because zero workspaces is a normal state and
`leave` already reached it from the other side; and whoever was sitting in the instance is
moved rather than stranded, which the `SET NULL` on the foreign key does not do by itself.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi import HTTPException

from server import runtime
from server import settings as server_settings
from server.auth import deps as auth_deps
from server.db import identity, repository
from server.db.models import Base, EDITOR, OWNER
from server.routers.workspaces import remove


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(runtime.bus, "publish", lambda *a, **k: None)
    yield session
    session.close()


def _workspace(db, slug: str):
    return repository.ensure_workspace(db, slug, slug.capitalize())


def _account(db, username: str, grants: list, active=None):
    user = identity.create_user(db, username=username, name=username, password_hash="x")
    for workspace, role in grants:
        identity.grant(db, workspace.id, user.id, role)
    if active is not None:
        user.active_workspace_id = active.id
    db.flush()
    return user


def _access(user, workspace, role=OWNER):
    return auth_deps.Access(
        user=user,
        workspace=workspace,
        role=role,
        ws=server_settings.workspace_for(workspace.slug),
    )


def test_the_owner_can_delete_the_last_workspace_of_the_installation(db):
    aula = _workspace(db, "aula")
    ana = _account(db, "ana", [(aula, OWNER)], active=aula)

    result = remove("aula", access=_access(ana, aula), db=db)

    assert result["deleted"] == "aula"
    assert repository.list_workspaces(db) == []


# The FK is `SET NULL`, so without rehoming the database lands everybody at «no workspace»
# — including the people who have another one to fall back to.
def test_whoever_was_inside_is_moved_to_a_workspace_they_belong_to(db):
    aula = _workspace(db, "aula")
    taller = _workspace(db, "taller")
    ana = _account(db, "ana", [(aula, OWNER)], active=aula)
    bruno = _account(db, "bruno", [(aula, EDITOR), (taller, EDITOR)], active=aula)

    result = remove("aula", access=_access(ana, aula), db=db)

    assert result["rehomed"]["bruno"] == "taller"
    assert bruno.active_workspace_id == taller.id
    assert ana.active_workspace_id is None


# The route resolves its access from the active workspace, so a slug that is not it would
# be deleting one instance while holding the permissions of another.
def test_only_the_active_workspace_is_deletable(db):
    aula = _workspace(db, "aula")
    taller = _workspace(db, "taller")
    ana = _account(db, "ana", [(aula, OWNER), (taller, OWNER)], active=aula)

    with pytest.raises(HTTPException) as raised:
        remove("taller", access=_access(ana, aula), db=db)

    assert raised.value.status_code == 409


# The deleter is themselves one of the stranded: they were standing in the instance they
# just removed, so «where do I land» has to be answered for them too and not only for the
# people who were sharing it.
def test_the_owner_lands_in_their_first_remaining_workspace(db):
    aula = _workspace(db, "aula")
    taller = _workspace(db, "taller")
    ana = _account(db, "ana", [(aula, OWNER), (taller, OWNER)], active=aula)

    result = remove("aula", access=_access(ana, aula), db=db)

    assert result["rehomed"]["ana"] == "taller"
    assert ana.active_workspace_id == taller.id
    assert auth_deps.current_workspace_for(db, ana) is taller
