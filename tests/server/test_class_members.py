"""The people of a subject: pausing, opening and removing them, and who may do it to whom.

A teacher pauses, opens and removes students; teachers and owners are the owner's to touch.
Pausing is reversible — the membership keeps its role, its origin and its date — and removing
is not. Whatever the gesture, the subject never loses its last active owner while it has
people (`last_owner`, at every door: the class's routes, leaving, the administrator's panel),
the person's jobs there stop, their tab lands elsewhere, an open socket of theirs closes with
4403, and their files stay where they are.
"""

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import auth, installation, members, singletons
from server import generations as store
from server.auth.deps import FORBIDDEN, Access
from server.db import identity, repository
from server.db.models import EDITOR, OWNER, VIEWER, Base
from server.jobs.bus import EventBus
from server.jobs.runner import JobRunner
from server.routers import admin as admin_routes
from server.routers import auth as auth_routes
from server.routers import members as member_routes
from server.routers import workspaces as workspace_routes
from server.routers import ws as ws_routes


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(identity, "now", datetime.now)
    yield session
    session.close()


@pytest.fixture
def stage(monkeypatch):
    """A bus that keeps what is said and a queue that never starts anything."""
    bus = EventBus(buffer_size=100)
    monkeypatch.setattr(EventBus, "_append_jsonl", lambda *a, **k: None)
    runner = JobRunner(bus, {"generate": lambda job, control: {}, "build_kg": lambda job, control: {}})
    monkeypatch.setattr(singletons, "bus", bus)
    monkeypatch.setattr(singletons, "runner", runner)
    return SimpleNamespace(bus=bus, runner=runner)


@pytest.fixture
def aula(db):
    """A subject with its owner, a second teacher and two students, all landed in it."""
    workspace = repository.ensure_workspace(db, "aula", "Aula")
    people = {}
    for username, role in (("ana", OWNER), ("bruno", EDITOR), ("carla", VIEWER), ("dani", VIEWER)):
        user = identity.create_user(db, username=username, name=username.title(), password_hash="x")
        identity.grant(db, workspace.id, user.id, role, via="invite", invited_by=None)
        user.active_workspace_id = workspace.id
        people[username] = user
    db.flush()
    return SimpleNamespace(workspace=workspace, **people)


def _access(db, user, workspace, level=VIEWER) -> Access:
    return auth.access_for(db, user, workspace, level)


def _refused(call) -> HTTPException:
    with pytest.raises(HTTPException) as refused:
        call()
    return refused.value


# THE LIST ---------------------------------------------------------------------------------------


def test_a_teacher_reads_the_people_and_how_they_came_in(db, aula, stage):
    members.disable_member(db, aula.workspace, aula.dani, aula.ana)

    listed = member_routes.listing(access=_access(db, aula.bruno, aula.workspace), db=db)["members"]
    by_name = {row["username"]: row for row in listed}

    assert set(by_name) == {"ana", "bruno", "carla", "dani"}
    assert by_name["carla"]["role"] == "viewer"
    assert by_name["carla"]["via"] == "invite"
    assert by_name["carla"]["disabled_at"] is None
    assert by_name["dani"]["disabled_at"] is not None
    assert by_name["carla"]["joined_at"]
    # Who and how, never what they did and never where to write to them.
    assert set(by_name["carla"]) == {
        "user_id", "name", "username", "role", "joined_at", "via", "invited_by", "disabled_at"
    }


def test_a_student_is_not_given_the_list(db, aula):
    refused = _refused(lambda: auth.access_for(db, aula.carla, aula.workspace, EDITOR))

    assert refused.status_code == 403
    assert refused.headers == {"X-Error-Code": auth.ROLE_TOO_LOW}


# WHO MAY DO WHAT TO WHOM ------------------------------------------------------------------------


def test_a_teacher_pauses_and_removes_students(db, aula, stage):
    access = _access(db, aula.bruno, aula.workspace)

    member_routes.disable(aula.carla.id, access=access, db=db)
    member_routes.remove(aula.dani.id, access=access, db=db)

    assert identity.membership(db, aula.workspace.id, aula.carla.id).disabled_at is not None
    assert identity.membership(db, aula.workspace.id, aula.dani.id) is None


@pytest.mark.parametrize("gesture", ["disable", "remove"])
def test_a_teacher_does_not_touch_another_teacher(db, aula, stage, gesture):
    access = _access(db, aula.bruno, aula.workspace)

    refused = _refused(lambda: getattr(member_routes, gesture)(aula.ana.id, access=access, db=db))

    assert refused.status_code == 403
    assert refused.headers == {"X-Error-Code": auth.ROLE_TOO_LOW}


def test_the_owner_pauses_and_removes_a_teacher(db, aula, stage):
    access = _access(db, aula.ana, aula.workspace)

    member_routes.disable(aula.bruno.id, access=access, db=db)
    member_routes.enable(aula.bruno.id, access=access, db=db)
    member_routes.remove(aula.bruno.id, access=access, db=db)

    assert identity.membership(db, aula.workspace.id, aula.bruno.id) is None


def test_an_owner_is_never_paused(db, aula, stage):
    identity.grant(db, aula.workspace.id, aula.bruno.id, OWNER)
    access = _access(db, aula.bruno, aula.workspace)

    refused = _refused(lambda: member_routes.disable(aula.ana.id, access=access, db=db))

    assert refused.status_code == 409
    assert refused.headers == {"X-Error-Code": members.OWNER_PAUSED}


def test_nobody_pauses_or_removes_themselves_here(db, aula, stage):
    access = _access(db, aula.bruno, aula.workspace)

    refused = _refused(lambda: member_routes.remove(aula.bruno.id, access=access, db=db))

    assert refused.status_code == 409
    assert refused.headers == {"X-Error-Code": "self"}


def test_a_stranger_is_a_404(db, aula, stage):
    outsider = identity.create_user(db, username="eva", name="Eva", password_hash="x")

    refused = _refused(
        lambda: member_routes.disable(outsider.id, access=_access(db, aula.ana, aula.workspace), db=db)
    )

    assert refused.status_code == 404


# THE LAST OWNER, AT EVERY DOOR ------------------------------------------------------------------


def _last_owner(refused: HTTPException) -> None:
    assert refused.status_code == 409
    assert refused.headers == {"X-Error-Code": members.LAST_OWNER}


def test_the_last_owner_does_not_step_down_while_people_remain(db, aula, stage):
    access = _access(db, aula.ana, aula.workspace)

    _last_owner(_refused(lambda: member_routes.change_role(
        aula.ana.id, member_routes.RoleBody(role="editor"), access=access, db=db
    )))


def test_the_last_owner_does_not_leave_while_people_remain(db, aula, stage):
    _last_owner(_refused(lambda: workspace_routes.leave("aula", user=aula.ana, db=db)))
    assert identity.membership(db, aula.workspace.id, aula.ana.id) is not None


def test_the_administrator_does_not_take_the_last_owner_out_either(db, aula, stage):
    admin = identity.create_user(db, username="root", name="Root", password_hash="x", is_admin=True)

    _last_owner(_refused(lambda: admin_routes.revoke_membership(aula.ana.id, "aula", admin=admin, db=db)))
    _last_owner(_refused(lambda: admin_routes.grant_membership(
        aula.ana.id, admin_routes.MembershipBody(workspace="aula", role="viewer"), db=db
    )))


def test_handing_over_the_ownership_keeps_an_owner_and_never_none(db, aula, stage):
    access = _access(db, aula.ana, aula.workspace)

    member_routes.change_role(aula.bruno.id, member_routes.RoleBody(role="owner"), access=access, db=db)
    member_routes.change_role(aula.ana.id, member_routes.RoleBody(role="editor"), access=access, db=db)

    roles = {m.user_id: m.role for m, _ in identity.members_of(db, aula.workspace.id)}
    assert roles[aula.bruno.id] == OWNER
    assert roles[aula.ana.id] == EDITOR


def test_the_last_person_of_all_still_leaves_and_takes_the_subject(db, stage):
    ws = installation.workspace_for("sola")
    installation.provision(ws)
    workspace = repository.ensure_workspace(db, "sola", "Sola")
    ana = identity.create_user(db, username="ana", name="Ana", password_hash="x")
    identity.grant(db, workspace.id, ana.id, OWNER)

    assert workspace_routes.leave("sola", user=ana, db=db)["deleted"] is True


def test_a_subject_with_no_owner_left_does_not_block_its_teachers(db, aula, stage):
    """Its owner's account was deleted: there is no owner to lose, and the panel marks it."""
    identity.revoke_membership(db, aula.workspace.id, aula.ana.id)

    member_routes.remove(aula.carla.id, access=_access(db, aula.bruno, aula.workspace), db=db)

    assert identity.membership(db, aula.workspace.id, aula.carla.id) is None


# WHAT A GESTURE SETS OFF ------------------------------------------------------------------------


@pytest.mark.parametrize("gesture", [members.disable_member, members.remove_member])
def test_a_closed_membership_stops_its_jobs_moves_its_tab_and_keeps_its_files(db, aula, stage, gesture):
    other = repository.ensure_workspace(db, "otra", "Otra")
    identity.grant(db, other.id, aula.carla.id, VIEWER)
    ws = installation.workspace_for("aula")
    saved = store.save(ws, aula.carla.id, "job1", 1, {"output": {"item": {"enunciado": "mío"}}})
    hers = stage.runner.submit("generate", {}, workspace="aula", user_id=aula.carla.id)
    build = stage.runner.submit("build_kg", {}, workspace="aula", user_id=aula.bruno.id)

    gesture(db, aula.workspace, aula.carla, aula.bruno)

    assert hers.status == "cancelled"
    assert build.status == "queued"
    assert aula.carla.active_workspace_id == other.id
    assert store.get(ws, aula.carla.id, saved) is not None


def test_a_closed_membership_is_announced_to_no_browser(db, aula, stage):
    members.remove_member(db, aula.workspace, aula.carla, aula.bruno)

    [event] = [e for e in stage.bus._buffer if e.kind == members.CLOSED_EVENT]
    assert event.payload == {"user_id": aula.carla.id, "gesture": members.REMOVED}
    assert event.workspace == "aula"
    for user_id in (aula.carla.id, aula.ana.id, None):
        assert not EventBus.visible(event, "aula", user_id)


# A PAUSED MEMBERSHIP ----------------------------------------------------------------------------


def test_a_paused_student_is_refused_everywhere_with_its_own_code(db, aula, stage):
    members.disable_member(db, aula.workspace, aula.carla, aula.bruno)

    refused = _refused(lambda: auth.access_for(db, aula.carla, aula.workspace, VIEWER))

    assert refused.status_code == 403
    assert refused.headers == {"X-Error-Code": auth.MEMBERSHIP_DISABLED}
    assert refused.detail == "Tu docente ha desactivado tu acceso a esta asignatura."


def test_a_paused_subject_leaves_the_switcher_and_is_never_landed_in(db, aula, stage):
    other = repository.ensure_workspace(db, "otra", "Otra")
    identity.grant(db, other.id, aula.carla.id, VIEWER)
    members.disable_member(db, aula.workspace, aula.carla, aula.bruno)
    aula.carla.active_workspace_id = aula.workspace.id  # a stale preference

    me = auth_routes._me(db, aula.carla)

    assert [row["slug"] for row in me["workspaces"]] == ["otra"]
    assert me["active_workspace"] == "otra"
    refused = _refused(lambda: workspace_routes.activate("aula", user=aula.carla, db=db))
    assert refused.headers == {"X-Error-Code": auth.MEMBERSHIP_DISABLED}


def test_opened_again_it_is_as_it_was(db, aula, stage):
    before = identity.membership(db, aula.workspace.id, aula.carla.id)
    joined, via = before.created_at, before.via
    ws = installation.workspace_for("aula")
    saved = store.save(ws, aula.carla.id, "job2", 1, {"output": {"item": {"enunciado": "sigue"}}})

    members.disable_member(db, aula.workspace, aula.carla, aula.bruno)
    members.enable_member(db, aula.workspace, aula.carla, aula.bruno)

    row = identity.membership(db, aula.workspace.id, aula.carla.id)
    assert (row.role, row.via, row.created_at, row.disabled_at) == (VIEWER, via, joined, None)
    assert auth.access_for(db, aula.carla, aula.workspace, VIEWER).role == VIEWER
    assert store.get(ws, aula.carla.id, saved) is not None


def test_a_paused_member_counts_for_no_owner_but_keeps_the_tree(db, aula, stage):
    """The owner may leave once only paused people remain; the subject and its files stay."""
    access = _access(db, aula.ana, aula.workspace)
    for user in (aula.bruno, aula.carla, aula.dani):
        member_routes.disable(user.id, access=access, db=db)

    left = workspace_routes.leave("aula", user=aula.ana, db=db)

    assert left["deleted"] is False
    assert repository.get_workspace(db, "aula") is not None


# SEVERAL AT ONCE --------------------------------------------------------------------------------


def test_a_bulk_gesture_says_what_it_did_and_what_it_refused(db, aula, stage):
    access = _access(db, aula.bruno, aula.workspace)

    answer = member_routes.bulk(
        member_routes.BulkBody(action="disable", user_ids=[aula.carla.id, aula.ana.id, aula.dani.id]),
        access=access,
        db=db,
    )

    assert answer["done"] == [aula.carla.id, aula.dani.id]
    assert [(row["user_id"], row["code"]) for row in answer["refused"]] == [
        (aula.ana.id, auth.ROLE_TOO_LOW)
    ]


# THE SOCKET -------------------------------------------------------------------------------------


class _Socket:
    """A WebSocket stand-in that records what it was sent and how it was closed."""

    def __init__(self):
        self.query_params = {}
        self.sent: list[dict] = []
        self.closed: int | None = None

    async def accept(self):
        pass

    async def send_json(self, message):
        self.sent.append(message)

    async def close(self, code: int = 1000):
        if self.closed is None:
            self.closed = code


def test_a_socket_closes_when_its_membership_does_and_no_other_does(monkeypatch):
    def access_of(user_id):
        return Access(
            user=SimpleNamespace(id=user_id),
            workspace=SimpleNamespace(slug="aula"),
            role=VIEWER,
            ws=None,
        )

    async def scenario():
        bus = EventBus(buffer_size=50)
        bus.attach_loop(asyncio.get_running_loop())
        monkeypatch.setattr(singletons, "bus", bus)
        monkeypatch.setattr(singletons, "runner", JobRunner(bus, {}))
        monkeypatch.setattr(ws_routes.middleware, "cross_site", lambda socket: False)
        sockets = {1: _Socket(), 2: _Socket()}
        monkeypatch.setattr(
            ws_routes, "authenticate_socket", lambda socket: access_of(1 if socket is sockets[1] else 2)
        )
        tasks = {user: asyncio.create_task(ws_routes.stream(socket)) for user, socket in sockets.items()}
        await asyncio.sleep(0.2)

        bus.publish_internal("aula", members.CLOSED_EVENT, {"user_id": 1, "gesture": "removed"})
        await asyncio.wait_for(tasks[1], 2)
        bus.publish("aula", None, "pipeline.changed", {"artifact": "knowledge_graph"})
        await asyncio.sleep(0.2)

        assert sockets[1].closed == FORBIDDEN
        assert sockets[2].closed is None
        assert [m["kind"] for m in sockets[2].sent] == ["stream.ready", "pipeline.changed"]
        tasks[2].cancel()

    asyncio.run(scenario())
