"""The groups of a subject's class: with a group a teacher does what they do with the class.

Open or close each tool to it, over the subject's switch; read its activity counted on its
students alone; give it its own progress; bring students into it with its own link. A
student is in one group at most, for now; a teacher is in none; pausing keeps the group.
"""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import activity, curriculum, groups, members
from server.auth import features, queries
from server.core import process
from server.db import repository
from server.db.models import EDITOR, OWNER, VIEWER, Base
from server.jobs.bus import EventBus
from server.jobs.runner import JobRunner
from server.members import Refusal
from server.routers import activity as activity_routes
from server.routers import kg as kg_routes
from server.routers import members as member_routes
from server.routers.members import BulkBody, GroupBody, UsesBody
from variatio.core.workspace import Workspace

from ..conftest import CHAIN_GRAPH


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(queries, "now", datetime.now)
    yield session
    session.close()


@pytest.fixture(autouse=True)
def stage(monkeypatch):
    """A bus that keeps what is said and a queue that never starts anything."""
    bus = EventBus(buffer_size=100)
    monkeypatch.setattr(process, "bus", bus)
    monkeypatch.setattr(process, "runner", JobRunner(bus, {}))


@pytest.fixture
def aula(db, tmp_path):
    """A subject with its owner, a teacher and three students, and another subject."""
    workspace = repository.ensure_workspace(db, "aula", "Programación I")
    other = repository.ensure_workspace(db, "otra", "Otra")
    people = {}
    for username, role in (("ana", OWNER), ("bruno", EDITOR), ("sara", VIEWER), ("diego", VIEWER), ("noa", VIEWER)):
        user = queries.create_user(
            db, username=username, name=username, password_hash="x",
            evaluator_profile="teacher" if role != VIEWER else "student",
        )
        queries.grant(db, workspace.id, user.id, role)
        people[username] = user
    db.flush()
    ws = Workspace(root=tmp_path / "aula", slug="aula")
    ws.artifacts_dir.mkdir(parents=True, exist_ok=True)
    ws.kg_path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    return SimpleNamespace(workspace=workspace, other=other, ws=ws, **people)


def _access(aula, user, role=OWNER):
    return SimpleNamespace(user=user, workspace=aula.workspace, role=role, ws=aula.ws)


def _group(db, aula, name: str):
    return groups.create(db, aula.workspace, name, aula.ana)


# MAKING THEM AND PUTTING STUDENTS IN ------------------------------------------------------------


def test_a_name_is_unique_in_its_subject(db, aula):
    _group(db, aula, "Grupo A")
    with pytest.raises(Refusal) as refused:
        _group(db, aula, "  grupo   a ")
    assert refused.value.code == groups.NAME_TAKEN
    groups.create(db, aula.other, "Grupo A", aula.ana)


def test_a_student_is_in_one_group_at_most_and_moving_them_keeps_the_rest(db, aula):
    first, second = _group(db, aula, "A"), _group(db, aula, "B")
    groups.place(db, aula.workspace, aula.sara, first)
    groups.place(db, aula.workspace, aula.sara, second)

    assert queries.group_of(db, aula.workspace.id, aula.sara.id).id == second.id
    assert groups.member_ids(db, first) == set()
    row = queries.membership(db, aula.workspace.id, aula.sara.id)
    assert row.role == VIEWER and row.active


def test_a_teacher_is_in_no_group(db, aula):
    with pytest.raises(Refusal) as refused:
        groups.place(db, aula.workspace, aula.bruno, _group(db, aula, "A"))
    assert refused.value.code == groups.NOT_A_STUDENT


def test_pausing_keeps_the_group_and_removing_takes_it(db, aula):
    group = _group(db, aula, "A")
    for student in (aula.sara, aula.diego):
        groups.place(db, aula.workspace, student, group)
    members.disable_member(db, aula.workspace, aula.sara, aula.ana)
    members.remove_member(db, aula.workspace, aula.diego, aula.ana)

    assert groups.member_ids(db, group) == {aula.sara.id}
    assert groups.sizes(db, aula.workspace) == {}


def test_the_bulk_gesture_puts_students_in_and_takes_them_out_person_by_person(db, aula):
    group = _group(db, aula, "A")
    access = _access(aula, aula.ana)
    answer = member_routes.bulk(
        BulkBody(action="group", user_ids=[aula.sara.id, aula.bruno.id], group_id=group.id), access=access, db=db
    )
    assert answer["done"] == [aula.sara.id]
    assert answer["refused"][0]["code"] == groups.NOT_A_STUDENT

    listing = member_routes.listing(access=access, db=db)
    by_name = {row["username"]: row for row in listing["members"]}
    assert by_name["sara"]["group"] == {"id": group.id, "name": "A"}
    assert by_name["noa"]["group"] is None
    assert listing["groups"][0]["students"] == 1

    member_routes.bulk(BulkBody(action="group", user_ids=[aula.sara.id], group_id=None), access=access, db=db)
    assert queries.group_of(db, aula.workspace.id, aula.sara.id) is None


def test_deleting_a_group_leaves_its_students_in_the_class_and_kills_its_link(db, aula):
    access = _access(aula, aula.ana)
    member_routes.create_group(GroupBody(name="A"), access=access, db=db)
    group = groups.all_of(db, aula.workspace)[0]
    groups.place(db, aula.workspace, aula.sara, group)
    link = queries.create_class_link(
        db, aula.workspace.id, "h1", datetime(2100, 1, 1), 10, group_id=group.id
    )

    member_routes.delete_group(group.id, access=access, db=db)

    assert queries.group_of(db, aula.workspace.id, aula.sara.id) is None
    assert queries.membership(db, aula.workspace.id, aula.sara.id).active
    assert link.revoked_at is not None


def test_another_subjects_group_is_unknown_here(db, aula):
    elsewhere = groups.create(db, aula.other, "Ajeno", aula.ana)
    with pytest.raises(HTTPException) as refused:
        member_routes.uses(group=elsewhere.id, access=_access(aula, aula.ana), db=db)
    assert refused.value.status_code == 404


# WHAT A GROUP USES ------------------------------------------------------------------------------


def test_a_groups_switch_says_first_and_none_is_the_subjects(db, aula):
    group = _group(db, aula, "A")
    groups.place(db, aula.workspace, aula.sara, group)

    def open_to(user):
        return features.refusal(db, user, features.GENERATE, aula.workspace, VIEWER) is None

    assert open_to(aula.sara) and open_to(aula.diego)
    groups.set_tools(db, group, {"generate": False})
    assert not open_to(aula.sara) and open_to(aula.diego)
    assert "grupo" in features.refusal(db, aula.sara, features.GENERATE, aula.workspace, VIEWER)

    features.set_subject_uses(db, aula.workspace, {features.GENERATE: False})
    groups.set_tools(db, group, {"generate": True})
    assert open_to(aula.sara) and not open_to(aula.diego)

    groups.set_tools(db, group, {"generate": None})
    assert not open_to(aula.sara)
    assert features.refusal(db, aula.bruno, features.GENERATE, aula.workspace, EDITOR) is None


def test_the_uses_route_reads_and_writes_a_group_in_three_states(db, aula):
    group = _group(db, aula, "A")
    access = _access(aula, aula.ana)
    answer = member_routes.change_uses(UsesBody(tutor=False), group=group.id, access=access, db=db)
    assert answer["group"]["tutor"] is False and answer["tutor"] is True
    answer = member_routes.change_uses(UsesBody(tutor=None), group=group.id, access=access, db=db)
    assert answer["group"]["tutor"] is None


# ITS ACTIVITY AND ITS PROGRESS ------------------------------------------------------------------


def test_a_groups_activity_counts_its_students_alone(db, aula, monkeypatch):
    group = _group(db, aula, "A")
    groups.place(db, aula.workspace, aula.sara, group)
    access = _access(aula, aula.ana)
    monkeypatch.setattr(activity, "TUTOR_READER", None)

    whole = activity_routes.weeks(student=None, group=None, access=access, db=db)
    part = activity_routes.weeks(student=None, group=group.id, access=access, db=db)

    assert {s["username"] for s in whole["students"]} == {"sara", "diego", "noa"}
    assert [s["username"] for s in part["students"]] == ["sara"]
    with pytest.raises(HTTPException) as refused:
        activity_routes.weeks(student=aula.diego.id, group=group.id, access=access, db=db)
    assert refused.value.status_code == 404


def test_a_groups_digest_is_its_own_file_or_the_class_cut(db, aula, tmp_path):
    assert activity.digest_path(aula.ws, "2026-W41", 7).name == "2026-W41.group-7.json"
    folder = aula.ws.root / "analytics" / "digest"
    folder.mkdir(parents=True)
    (folder / "2026-W40.json").write_text("{}", encoding="utf-8")
    (folder / "2026-W41.group-7.json").write_text("{}", encoding="utf-8")
    assert activity.digested_weeks(aula.ws) == {"2026-W40"}
    assert activity.digested_weeks(aula.ws, 7) == {"2026-W40", "2026-W41"}


def test_a_group_may_follow_its_own_progress_and_its_student_reads_it(db, aula):
    group = _group(db, aula, "A")
    groups.place(db, aula.workspace, aula.sara, group)
    teacher = _access(aula, aula.ana)
    kg_routes.write_curriculum(kg_routes.CurriculumBody(concepts=["Variable"]), access=teacher, db=db)
    kg_routes.write_curriculum(
        kg_routes.CurriculumBody(concepts=["Función"], group=group.id), access=teacher, db=db
    )

    sara = kg_routes.read_curriculum(access=_access(aula, aula.sara, VIEWER), db=db)
    diego = kg_routes.read_curriculum(access=_access(aula, aula.diego, VIEWER), db=db)
    assert sara["concepts"] == ["Función"] and sara["own"] is True
    assert diego["concepts"] == ["Variable"] and diego["own"] is False

    kg_routes.write_curriculum(
        kg_routes.CurriculumBody(group=group.id, follow_subject=True), access=teacher, db=db
    )
    assert kg_routes.read_curriculum(access=_access(aula, aula.sara, VIEWER), db=db)["concepts"] == ["Variable"]
    assert curriculum.of_group(aula.ws, group, _graph(aula))["own"] is False


def _graph(aula):
    from variatio.loaders.knowledge_graph import KnowledgeGraph

    return KnowledgeGraph(str(aula.ws.kg_path))


# ITS LINK ---------------------------------------------------------------------------------------


def test_each_destination_has_its_own_live_link(db, aula):
    group = _group(db, aula, "A")
    whole = queries.create_class_link(db, aula.workspace.id, "h1", datetime(2100, 1, 1), 10)
    part = queries.create_class_link(db, aula.workspace.id, "h2", datetime(2100, 1, 1), 10, group_id=group.id)

    assert queries.live_class_link(db, aula.workspace.id).id == whole.id
    assert queries.live_class_link(db, aula.workspace.id, group.id).id == part.id
    queries.revoke_class_link(db, part)
    assert queries.live_class_link(db, aula.workspace.id).id == whole.id


def test_entering_through_a_groups_link_puts_the_student_in_it(db, aula):
    group = _group(db, aula, "A")
    newcomer = queries.create_user(db, username="leo", name="Leo", password_hash="x", evaluator_profile="student")
    queries.grant(db, aula.workspace.id, newcomer.id, VIEWER)
    groups.place_on_entry(db, aula.workspace.id, newcomer.id, group.id)
    assert queries.group_of(db, aula.workspace.id, newcomer.id).id == group.id

    groups.place_on_entry(db, aula.workspace.id, aula.bruno.id, group.id)
    assert queries.group_of(db, aula.workspace.id, aula.bruno.id) is None


def test_ending_the_course_pauses_every_live_link(db, aula):
    group = _group(db, aula, "A")
    whole = queries.create_class_link(db, aula.workspace.id, "h1", datetime(2100, 1, 1), 10)
    part = queries.create_class_link(db, aula.workspace.id, "h2", datetime(2100, 1, 1), 10, group_id=group.id)
    members.end_course(db, aula.workspace, aula.ana, "disable")
    assert whole.paused_at is not None and part.paused_at is not None
