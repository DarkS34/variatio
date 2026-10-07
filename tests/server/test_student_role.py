"""What a student of a subject (`viewer`) may do with the queue, and how a refusal reads.

A student queues a commission or a comparison and cancels their own; everything else on the
queue — a build, a transcription, a tagging — is the construction's and takes a teacher. A
refusal carries a stable code (`role_too_low`, `not_member`), because the client tells the
cases apart by code and never by sentence. And a student's `force` is no way round the
construction: what a commission reads before the subject is closed is a subject still being
corrected.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from evaluation.api import router as evaluation_router
from server import auth, features, installation, singletons
from server.auth.deps import Access
from server.db import identity, repository
from server.db.models import EDITOR, OWNER, VIEWER, Base
from server.jobs.bus import EventBus
from server.jobs.runner import JobRunner
from server.routers import jobs as jobs_router

ANA, LUIS = 1, 2


# THE CODES OF A REFUSAL --------------------------------------------------------------------


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def _member(db, username: str, workspace, role: str | None, admin: bool = False):
    user = identity.create_user(db, username=username, name=username, password_hash="x")
    user.is_admin = admin
    if role is not None:
        identity.grant(db, workspace.id, user.id, role)
    db.flush()
    return user


def test_an_account_with_no_membership_is_told_so_by_code(db):
    aula = repository.ensure_workspace(db, "aula", "Aula")
    nadie = _member(db, "nadie", aula, None)

    with pytest.raises(HTTPException) as refused:
        auth.access_for(db, nadie, aula, VIEWER)

    assert refused.value.status_code == 403
    assert refused.value.headers == {"X-Error-Code": auth.NOT_MEMBER}


def test_a_member_below_the_level_is_told_so_by_code(db):
    aula = repository.ensure_workspace(db, "aula", "Aula")
    alumna = _member(db, "alumna", aula, VIEWER)

    with pytest.raises(HTTPException) as refused:
        auth.access_for(db, alumna, aula, EDITOR)

    assert refused.value.status_code == 403
    assert refused.value.headers == {"X-Error-Code": auth.ROLE_TOO_LOW}


def test_at_least_reads_the_role_and_the_administrators_bypass(db):
    aula = repository.ensure_workspace(db, "aula", "Aula")
    alumna = _member(db, "alumna", aula, VIEWER)
    docente = _member(db, "docente", aula, EDITOR)
    admin = _member(db, "admin", aula, VIEWER, admin=True)

    def reached(user, minimum):
        return auth.at_least(auth.access_for(db, user, aula, VIEWER), minimum)

    assert reached(alumna, VIEWER) is True
    assert reached(alumna, EDITOR) is False
    assert reached(docente, EDITOR) is True
    assert reached(docente, OWNER) is False
    # An administrator who is a student of the subject still reaches every level: the bypass
    # is resolved once, in `access_for`, and `at_least` only compares roles.
    assert reached(admin, OWNER) is True


def test_an_administrators_role_is_the_owners_whatever_the_membership(db):
    aula = repository.ensure_workspace(db, "aula", "Aula")
    admin = _member(db, "admin", aula, VIEWER, admin=True)

    enough = auth.access_for(db, admin, aula, VIEWER)
    bypassed = auth.access_for(db, admin, aula, EDITOR)

    assert (enough.role, enough.as_admin) == (OWNER, False)
    assert (bypassed.role, bypassed.as_admin) == (OWNER, True)


# THE QUEUE, BY ROLE ------------------------------------------------------------------------


@pytest.fixture
def queue(monkeypatch):
    """A runner that queues and never starts anything, with every gate of the chain open."""
    monkeypatch.setattr(EventBus, "_append_jsonl", lambda *a, **k: None)
    kinds = ("generate", "evaluate", "build_kg", "transcribe", "tag", "index")
    runner = JobRunner(EventBus(buffer_size=100), {kind: lambda job, control: {} for kind in kinds})
    monkeypatch.setattr(singletons, "runner", runner)
    monkeypatch.setattr(jobs_router.inference, "is_available", lambda: True)
    monkeypatch.setattr(jobs_router, "gate_error", lambda ws, kind: None)
    monkeypatch.setattr(jobs_router, "transcription_error", lambda ws, kind: None)
    return runner


def _access(role: str, user_id: int = ANA) -> Access:
    return Access(
        user=SimpleNamespace(id=user_id, name=f"cuenta {user_id}", is_admin=False),
        workspace=SimpleNamespace(id=1, slug="aula", name="Aula"),
        role=role,
        ws=installation.workspace_for("aula"),
    )


def _submit(kind: str, role: str, **body) -> dict:
    return jobs_router.submit(
        jobs_router.JobBody(kind=kind, **body), access=_access(role), db=None
    )


def test_a_student_queues_a_commission_and_it_is_redacted(queue):
    answer = _submit("generate", VIEWER)

    job = queue.get(answer["job"]["id"])
    assert job.kind == "generate"
    assert job.user_id == ANA
    assert job.redacted is True


def test_a_teachers_commission_is_not_redacted(queue):
    answer = _submit("generate", EDITOR)

    assert queue.get(answer["job"]["id"]).redacted is False


@pytest.mark.parametrize("kind", ["build_kg", "transcribe", "tag", "index"])
def test_the_constructions_jobs_take_a_teacher(queue, kind):
    with pytest.raises(HTTPException) as refused:
        _submit(kind, VIEWER)

    assert refused.value.status_code == 403
    assert refused.value.headers == {"X-Error-Code": auth.ROLE_TOO_LOW}
    assert queue.all() == []


def test_a_teacher_queues_the_constructions_jobs(queue):
    assert _submit("build_kg", EDITOR)["job"]["kind"] == "build_kg"


def test_a_student_queues_a_comparison_when_the_evaluation_is_open_to_them(queue, monkeypatch):
    monkeypatch.setattr(features, "enabled", lambda session, user, feature: True)

    answer = _submit("evaluate", VIEWER)

    assert queue.get(answer["job"]["id"]).redacted is True


def test_a_students_force_is_no_way_round_the_construction(queue, monkeypatch):
    monkeypatch.setattr(jobs_router, "gate_error", lambda ws, kind: "Falta cerrar el temario.")

    with pytest.raises(HTTPException) as refused:
        _submit("generate", VIEWER, force=True)
    assert refused.value.status_code == 409

    assert _submit("generate", EDITOR, force=True)["job"]["kind"] == "generate"


def test_a_comparisons_force_is_a_teachers_too(monkeypatch):
    monkeypatch.setattr(evaluation_router, "gate_error", lambda ws, kind: "Falta cerrar el temario.")
    body = evaluation_router.EvaluationBody(concepts=["Bucles"], force=True)

    with pytest.raises(HTTPException) as refused:
        evaluation_router.launch(body, access=_access(VIEWER))

    assert refused.value.status_code == 409


def test_a_students_comparison_is_redacted(queue, monkeypatch):
    monkeypatch.setattr(evaluation_router, "gate_error", lambda ws, kind: None)
    monkeypatch.setattr(evaluation_router.kg_edit, "load_graph", lambda ws: None)
    monkeypatch.setattr(evaluation_router.curriculum_store, "resolve", lambda ws, graph, asked: [])
    body = evaluation_router.EvaluationBody(concepts=["Bucles"])

    answer = evaluation_router.launch(body, access=_access(VIEWER))

    assert queue.get(answer["job"]["id"]).redacted is True


# CANCELLING --------------------------------------------------------------------------------


def test_a_student_stops_their_own_commission(queue):
    job = queue.submit("generate", {}, workspace="aula", user_id=ANA)

    assert jobs_router.cancel(job.id, access=_access(VIEWER)) == {"cancelled": True}


def test_a_student_does_not_stop_the_subjects_build(queue):
    build = queue.submit("build_kg", {}, workspace="aula", user_id=LUIS)

    with pytest.raises(HTTPException) as refused:
        jobs_router.cancel(build.id, access=_access(VIEWER))

    assert refused.value.status_code == 403
    assert refused.value.headers == {"X-Error-Code": auth.ROLE_TOO_LOW}
    assert build.status == "queued"


def test_a_teacher_stops_a_build_somebody_else_queued(queue):
    build = queue.submit("build_kg", {}, workspace="aula", user_id=LUIS)

    assert jobs_router.cancel(build.id, access=_access(EDITOR)) == {"cancelled": True}


def test_nobody_reaches_another_accounts_commission_to_stop_it(queue):
    hers = queue.submit("generate", {}, workspace="aula", user_id=LUIS)

    for role in (VIEWER, EDITOR, OWNER):
        with pytest.raises(HTTPException) as refused:
            jobs_router.cancel(hers.id, access=_access(role))
        assert refused.value.status_code == 404
    assert hers.status == "queued"
