"""The owner disposing of one of their own instances.

The LAST workspace of the installation is deletable, zero workspaces being a normal state,
and whoever was sitting in the instance is MOVED rather than stranded — which the `SET NULL`
on the foreign key does not do by itself.

Who else is in it decides whether the directory tree goes with the row: the same condition
`leave` applies, arrived at from the other side.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi import HTTPException

from server import singletons
from server import installation
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
    monkeypatch.setattr(singletons.bus, "publish", lambda *a, **k: None)
    yield session
    session.close()


# The row AND the tree: half of what this file pins is which deletions take the second one
# with them. The suite's autouse fixture has already moved `WORKSPACES_DIR` into a tmp
# directory, so this writes nowhere near the installation's own instances.
def _workspace(db, slug: str):
    ws = installation.workspace_for(slug)
    installation.provision(ws)
    (ws.raw_corpus_dir / "apuntes.md").write_text("# Apuntes", encoding="utf-8")
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
        ws=installation.workspace_for(workspace.slug),
    )


def test_the_owner_can_delete_the_last_workspace_of_the_installation(db):
    aula = _workspace(db, "aula")
    ana = _account(db, "ana", [(aula, OWNER)], active=aula)

    result = remove("aula", access=_access(ana, aula), db=db)

    assert result["deleted"] == "aula"
    assert repository.list_workspaces(db) == []


# The FK is `SET NULL`, so without rehoming the database lands everybody at "no workspace"
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
# just removed, so "where do I land" has to be answered for them too and not only for the
# people who were sharing it.
def test_the_owner_lands_in_their_first_remaining_workspace(db):
    aula = _workspace(db, "aula")
    taller = _workspace(db, "taller")
    ana = _account(db, "ana", [(aula, OWNER), (taller, OWNER)], active=aula)

    result = remove("aula", access=_access(ana, aula), db=db)

    assert result["rehomed"]["ana"] == "taller"
    assert ana.active_workspace_id == taller.id
    assert auth_deps.current_workspace_for(db, ana) is taller


# Nobody left, nothing kept: leaving the tree standing after the only member disposes of the
# instance piles up hundreds of megabytes under a slug the installation no longer records
# anywhere, and only an administrator could ever say what any one of those directories was.
def test_deleting_an_instance_only_you_hold_takes_its_files(db):
    aula = _workspace(db, "aula")
    ana = _account(db, "ana", [(aula, OWNER)], active=aula)

    result = remove("aula", access=_access(ana, aula), db=db)

    assert result["files_removed"] is True
    assert not installation.workspace_for("aula").root.exists()


# The other side of the same condition, and the reason it is a condition at all: those raw
# documents are the OTHER person's, they are losing the instance without having asked, and a
# web request that silently takes their lecture notes with it is not one anybody expects to
# be irreversible. An administrator finishes the job from "Administración".
def test_deleting_one_other_people_are_in_leaves_their_files(db):
    aula = _workspace(db, "aula")
    ana = _account(db, "ana", [(aula, OWNER)], active=aula)
    _account(db, "bruno", [(aula, EDITOR)], active=aula)

    result = remove("aula", access=_access(ana, aula), db=db)

    assert result["files_removed"] is False
    assert (installation.workspace_for("aula").raw_corpus_dir / "apuntes.md").exists()


# An administrator reaches this through the bypass and holds no membership row, so "is
# anybody else in it" is the whole roster for them — not "is it empty of members".
def test_an_administrator_deleting_a_workspace_with_a_member_leaves_its_files(db):
    aula = _workspace(db, "aula")
    _account(db, "ana", [(aula, OWNER)], active=aula)
    root = _account(db, "root", [])

    result = remove("aula", access=_access(root, aula), db=db)

    assert result["files_removed"] is False
    assert (installation.workspace_for("aula").raw_corpus_dir / "apuntes.md").exists()


# The tree first, as in `DELETE /api/admin/workspaces/{slug}`: a failure leaves the row
# standing and the call retryable. The other order strands files nobody is on record as
# owning, which is the exact state this deletion exists to stop creating.
def test_a_tree_that_cannot_be_removed_leaves_the_row_standing(db, monkeypatch):
    aula = _workspace(db, "aula")
    ana = _account(db, "ana", [(aula, OWNER)], active=aula)

    def refuse(ws):
        raise OSError("dispositivo ocupado")

    monkeypatch.setattr(installation, "destroy", refuse)

    with pytest.raises(HTTPException) as raised:
        remove("aula", access=_access(ana, aula), db=db)

    assert raised.value.status_code == 409
    assert repository.get_workspace(db, "aula") is not None
