"""Leaving a workspace, which is only sometimes the same act as deleting it.

`DELETE /api/workspaces/{slug}` is the owner disposing of a shared instance. This is a
person disposing of their own access, and the two collapse into one exactly when the person
leaving is the last one linked to it: with the seat empty there is nobody left for the
workspace to belong to.

What the tests pin is the arithmetic of that «exactly when», the two states the register
calls normal — an installation with no workspaces, an account belonging to none — and what
happens to the DIRECTORY TREE on each side of it: it goes when the seat it belonged to
empties, because otherwise abandoned instances pile up under slugs that are on record
nowhere, and it stays untouched when somebody merely walks out of a shared one.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi import HTTPException

from server import settings
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


# The row AND the tree, because that pairing is half of what this file is about. The suite's
# autouse fixture has already moved `WORKSPACES_DIR` into a tmp directory, so `provision`
# writes nowhere near the installation's own instances.
def _workspace(db, slug: str):
    ws = settings.workspace_for(slug)
    settings.provision(ws)
    (ws.raw_corpus_dir / "apuntes.md").write_text("# Apuntes", encoding="utf-8")
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
    # And the files go too: with nobody left holding it, what would survive is orphaned
    # weight under a slug the installation no longer records anywhere.
    assert result["files_removed"] is True
    assert not settings.workspace_for("aula").root.exists()


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
    # Nothing on disk moves: the instance still belongs to somebody, and one person walking
    # out of it is not a reason to delete what the rest are working on.
    assert (settings.workspace_for("aula").raw_corpus_dir / "apuntes.md").exists()


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


def test_a_tree_that_cannot_be_removed_leaves_the_row_standing(db, monkeypatch):
    # The order is the point, and it is `DELETE /api/admin/workspaces/{slug}`'s: the tree
    # first, so a failure is retryable. Deleting the row first would strand the files whose
    # owner is no longer on record — the exact state this deletion exists to prevent.
    aula = _workspace(db, "aula")
    ana = _account(db, "ana", [(aula, OWNER)], active=aula)

    def refuse(ws):
        raise OSError("dispositivo ocupado")

    monkeypatch.setattr(settings, "destroy", refuse)

    with pytest.raises(HTTPException) as raised:
        leave("aula", user=ana, db=db)

    assert raised.value.status_code == 409
    assert repository.get_workspace(db, "aula") is not None
    assert identity.membership(db, aula.id, ana.id) is not None
