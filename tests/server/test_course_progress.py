"""What a class has covered, and what its students may use: the teachers decide both.

The course's progress («Avance del curso») bounds nobody: a commission's own list replaces
it, an empty one lifts it, and a student may run ahead of the class. Two switches of the subject close generating and the tutor
to its students — during an exam, say — and never to its teachers.
"""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import activity, curriculum, features
from server.auth.deps import require_feature
from server.db import identity, repository
from server.db.models import EDITOR, OWNER, VIEWER, Base
from server.routers import jobs as jobs_routes
from server.routers import members as member_routes
from server.routers.auth import _me
from server.routers.members import UsesBody
from variatio.core.workspace import Workspace
from variatio.instance.knowledge_graph import KnowledgeGraph

from ..conftest import CHAIN_GRAPH


def _subject(tmp_path):
    ws = Workspace(root=tmp_path, slug="aula")
    ws.instance_dir.mkdir(parents=True, exist_ok=True)
    ws.kg_path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    return ws, KnowledgeGraph(str(ws.kg_path))


# THE COURSE'S PROGRESS ---------------------------------------------------------------------


def test_the_progress_is_a_default_and_never_a_bound(tmp_path):
    ws, graph = _subject(tmp_path)
    curriculum.save(ws, ["Función", "Variable"], graph)

    assert curriculum.resolve(ws, graph, None) == ["Función", "Variable"]
    assert curriculum.resolve(ws, graph, []) == []
    assert curriculum.resolve(ws, graph, ["Memoización"]) == [
        "Función",
        "Memoización",
        "Recursividad",
        "Variable",
    ]


# WHAT THE STUDENTS USE ---------------------------------------------------------------------


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
def aula(db, tmp_path):
    """A subject with its owner, a teacher and a student."""
    workspace = repository.ensure_workspace(db, "aula", "Programación I")
    people = {}
    for username, role, profile in (
        ("ana", OWNER, "teacher"),
        ("bruno", EDITOR, "teacher"),
        ("sara", VIEWER, "student"),
    ):
        user = identity.create_user(
            db, username=username, name=username, password_hash="x", evaluator_profile=profile
        )
        identity.grant(db, workspace.id, user.id, role)
        people[username] = user
    db.flush()
    ws = Workspace(root=tmp_path / "aula", slug="aula")
    return SimpleNamespace(workspace=workspace, ws=ws, **people)


def _access(aula, user, role):
    return SimpleNamespace(user=user, workspace=aula.workspace, role=role, ws=aula.ws)


def test_a_subject_opens_both_to_its_students_until_a_teacher_closes_one(db, aula):
    features.set_mode(db, features.TUTOR, features.ALL)

    assert features.for_user(db, aula.sara, aula.workspace, VIEWER) == {
        "generate": True,
        "evaluation": False,
        "tutor": True,
    }

    member_routes.change_uses(UsesBody(generate=False), access=_access(aula, aula.bruno, EDITOR), db=db)

    assert features.for_user(db, aula.sara, aula.workspace, VIEWER)["generate"] is False
    assert features.for_user(db, aula.bruno, aula.workspace, EDITOR)["generate"] is True
    assert features.for_user(db, aula.sara, aula.workspace, VIEWER)["tutor"] is True


def test_a_closed_generation_refuses_a_student_s_commission_and_not_a_teacher_s(db, aula):
    member_routes.change_uses(UsesBody(generate=False), access=_access(aula, aula.ana, OWNER), db=db)
    body = jobs_routes.JobBody(kind="generate", params={"n": 1})

    with pytest.raises(HTTPException) as refused:
        jobs_routes.submit(body, access=_access(aula, aula.sara, VIEWER), db=db)

    assert refused.value.status_code == 403
    assert refused.value.headers == {"X-Error-Code": features.OFF_CODE}
    assert "cerrado la generación" in refused.value.detail
    assert features.refusal(db, aula.bruno, features.GENERATE, aula.workspace, EDITOR) is None


def test_a_closed_tutor_refuses_its_routes_to_a_student_alone(db, aula):
    features.set_mode(db, features.TUTOR, features.ALL)
    member_routes.change_uses(UsesBody(tutor=False), access=_access(aula, aula.ana, OWNER), db=db)
    check = require_feature(features.TUTOR)

    with pytest.raises(HTTPException) as refused:
        check(access=_access(aula, aula.sara, VIEWER), session=db)

    assert refused.value.headers == {"X-Error-Code": features.OFF_CODE}
    assert check(access=_access(aula, aula.bruno, EDITOR), session=db) is None


def test_the_administrator_s_switch_comes_before_the_subject_s(db, aula):
    member_routes.change_uses(UsesBody(tutor=True), access=_access(aula, aula.ana, OWNER), db=db)

    assert features.refusal(db, aula.sara, features.TUTOR, aula.workspace, VIEWER) == (
        features.REFUSALS[features.TUTOR]
    )


def test_the_session_reads_the_switches_of_the_subject_the_account_is_in(db, aula):
    aula.sara.active_workspace_id = aula.workspace.id
    member_routes.change_uses(UsesBody(generate=False), access=_access(aula, aula.ana, OWNER), db=db)

    assert _me(db, aula.sara)["features"]["generate"] is False


def test_the_tutor_switch_is_offered_only_where_a_student_may_use_the_tutor(db, aula):
    teacher = _access(aula, aula.ana, OWNER)

    assert member_routes.uses(access=teacher, db=db)["tutor_offered"] is False

    features.set_mode(db, features.TUTOR, features.SELECTED)
    features.set_listed(db, features.TUTOR, [aula.bruno.id])
    assert member_routes.uses(access=teacher, db=db)["tutor_offered"] is False

    features.set_listed(db, features.TUTOR, [aula.sara.id])
    assert member_routes.uses(access=teacher, db=db) == {
        "generate": True,
        "tutor": True,
        "tutor_installed": activity.tutor_installed(),
        "tutor_offered": True,
    }


def test_the_answer_says_whether_the_tutor_is_installed(db, aula, monkeypatch):
    # The screen draws the tutor's switch wherever the tutor is installed, offered or not.
    teacher = _access(aula, aula.ana, OWNER)
    monkeypatch.setattr(activity, "TUTOR_READER", None)
    assert member_routes.uses(access=teacher, db=db)["tutor_installed"] is False
    monkeypatch.setattr(activity, "TUTOR_READER", lambda ws, ids: None)
    assert member_routes.uses(access=teacher, db=db)["tutor_installed"] is True
