"""The tutor's routes: a conversation is its author's, a reply is a queued job, criteria are teachers'.

The queue here is a fresh runner that is never started, so a submitted turn stays queued —
which is exactly the state the rules about one reply at a time are about.
"""

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from server import auth, installation, singletons
from server.auth.deps import Access
from server.db import identity, repository
from server.jobs.bus import EventBus
from server.jobs.runner import JobRunner
from tutor import paths
from tutor.api import admin as admin_module
from tutor.api import jobs
from tutor.api import router as router_module
from tutor.api import store
from variatio.core.workspace import Workspace

from ..conftest import CHAIN_GRAPH

ANA, BEA = 1, 2


@pytest.fixture
def ws(tmp_path):
    ws = Workspace(tmp_path / "ws", slug="ws")
    ws.instance_dir.mkdir(parents=True)
    ws.kg_path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    return ws


@pytest.fixture
def runner(monkeypatch):
    idle = lambda job, control: None  # noqa: E731
    fresh = JobRunner(EventBus(), {jobs.TURN: idle, jobs.CRITERIA: idle})
    monkeypatch.setattr(singletons, "runner", fresh)
    monkeypatch.setattr(router_module.inference, "is_available", lambda: True)
    monkeypatch.setattr(router_module, "_chain_error", lambda access: None)
    return fresh


def client(ws, *, user_id=ANA, role="viewer") -> TestClient:
    access = Access(
        user=SimpleNamespace(id=user_id, name="Ana", username="ana"),
        workspace=SimpleNamespace(id=1, slug="ws", name="WS"),
        role=role,
        ws=ws,
    )

    def edit():
        if role == "viewer":
            raise HTTPException(403, "Tu rol no permite esta acción.")
        return access

    app = FastAPI()
    app.include_router(router_module.router)
    app.dependency_overrides[auth.VIEW.dependency] = lambda: access
    app.dependency_overrides[auth.EDIT.dependency] = edit
    return TestClient(app)


def opened(ws, user_id=ANA, message="¿Qué es la recursividad?"):
    response = client(ws, user_id=user_id).post("/api/tutor/conversations", json={"message": message})
    assert response.status_code == 201, response.text
    return response.json()


# CONVERSATIONS -----------------------------------------------------------------------------------


def test_a_student_opens_a_conversation_and_its_reply_is_queued_without_its_text(ws, runner):
    body = opened(ws)

    conversation, job = body["conversation"], body["job"]
    assert conversation["turns"][0]["text"] == "¿Qué es la recursividad?"
    assert conversation["pending"]["status"] == "queued"
    assert job["kind"] == jobs.TURN
    assert job["params"] == {"conversation": conversation["id"], "turn": 0}
    assert (store.author_dir(ws, ANA) / f"{conversation['id']}.json").is_file()


def test_a_second_message_waits_for_the_first_reply(ws, runner):
    conversation = opened(ws)["conversation"]

    second = client(ws).post(
        f"/api/tutor/conversations/{conversation['id']}/messages", json={"message": "¿Y bien?"}
    )

    assert second.status_code == 409


def test_one_reply_at_a_time_per_account_across_conversations(ws, runner):
    opened(ws)

    another = client(ws).post("/api/tutor/conversations", json={"message": "Otra duda"})

    assert another.status_code == 409
    assert len(store.list_for(ws, ANA)) == 1, "a refused turn writes nothing"


def test_another_account_finds_nothing_whatever_it_asks(ws, runner):
    conversation_id = opened(ws)["conversation"]["id"]
    bea = client(ws, user_id=BEA)

    assert bea.get("/api/tutor/conversations").json()["conversations"] == []
    for method, path in (
        ("get", f"/api/tutor/conversations/{conversation_id}"),
        ("delete", f"/api/tutor/conversations/{conversation_id}"),
        ("get", "/api/tutor/conversations/../../etc"),
    ):
        assert getattr(bea, method)(path).status_code == 404, path


def test_a_reply_cancelled_in_the_queue_frees_the_conversation_and_can_be_asked_again(ws, runner):
    conversation_id = opened(ws)["conversation"]["id"]
    ana = client(ws)

    assert ana.delete(f"/api/tutor/conversations/{conversation_id}/turn").json() == {"cancelled": True}
    detail = ana.get(f"/api/tutor/conversations/{conversation_id}").json()
    assert detail["pending"] is None
    assert detail["turns"][0]["failed"] == "cancelled"

    again = ana.post(f"/api/tutor/conversations/{conversation_id}/retry")
    assert again.status_code == 200, again.text
    assert again.json()["conversation"]["pending"]["status"] == "queued"


def test_a_reply_lost_to_a_restart_is_marked_and_frees_the_conversation(ws, runner):
    record = store.create(ws, ANA, "¿Hola?")
    record["pending"] = {"job_id": "nolongerknown", "turn": 0}
    store.write(ws, ANA, record)

    detail = client(ws).get(f"/api/tutor/conversations/{record['id']}").json()

    assert detail["pending"] is None and detail["turns"][0]["failed"] == "interrupted"


def test_an_empty_or_overlong_message_is_refused_before_anything_is_written(ws, runner):
    ana = client(ws)

    assert ana.post("/api/tutor/conversations", json={"message": "   "}).status_code == 422
    assert ana.post("/api/tutor/conversations", json={"message": "x" * 100_000}).status_code == 422
    assert store.list_for(ws, ANA) == []


def test_a_conversation_is_deleted_only_once_no_reply_is_on_its_way(ws, runner):
    conversation_id = opened(ws)["conversation"]["id"]
    ana = client(ws)

    assert ana.delete(f"/api/tutor/conversations/{conversation_id}").status_code == 409
    ana.delete(f"/api/tutor/conversations/{conversation_id}/turn")
    assert ana.delete(f"/api/tutor/conversations/{conversation_id}").json() == {"deleted": conversation_id}


# CRITERIA ----------------------------------------------------------------------------------------


def test_a_student_cannot_read_or_touch_the_criteria(ws, runner):
    viewer = client(ws, role="viewer")

    assert viewer.get("/api/tutor/criteria").status_code == 403
    assert viewer.put("/api/tutor/criteria", json={"criteria": {}}).status_code == 403
    assert viewer.post("/api/tutor/criteria/build").status_code == 403
    assert viewer.get("/api/tutor").json()["can_edit"] is False


def test_a_teacher_reads_the_units_and_saves_a_correction_and_never_the_method_s_rules(ws, runner):
    teacher = client(ws, role="editor")

    first = teacher.get("/api/tutor/criteria").json()
    assert first["origin"] == "missing"
    assert "fixed_rules" not in first, "the method's rules live in the prompt alone"
    assert [u["name"] for u in first["units"]] == ["Fundamentos", "Avanzado"]

    saved = teacher.put(
        "/api/tutor/criteria",
        json={"criteria": {"general": [{"text": "Sin break.", "strength": "must"}], "units": {"Nada": []}}},
    ).json()
    assert saved["origin"] == "curated"
    assert saved["criteria"]["general"][0]["text"] == "Sin break."
    assert saved["warnings"]
    assert paths.criteria_path(ws).is_file()
    assert teacher.get("/api/tutor").json()["criteria"]["origin"] == "curated"


def test_the_criteria_are_drafted_by_one_job_at_a_time(ws, runner):
    teacher = client(ws, role="editor")

    first = teacher.post("/api/tutor/criteria/build")
    assert first.status_code == 200 and first.json()["job"]["kind"] == jobs.CRITERIA
    assert teacher.post("/api/tutor/criteria/build").status_code == 409
    assert teacher.put("/api/tutor/criteria", json={"criteria": {}}).status_code == 409


# THE ADMINISTRATOR -------------------------------------------------------------------------------


@pytest.fixture
def admin(ws, monkeypatch):
    users = [SimpleNamespace(id=ANA, username="ana", name="Ana")]
    monkeypatch.setattr(repository, "get_workspace", lambda db, slug: object() if slug == "ws" else None)
    monkeypatch.setattr(identity, "list_users", lambda db: users)
    monkeypatch.setattr(installation, "workspace_for", lambda slug: ws)
    app = FastAPI()
    app.include_router(admin_module.router)
    app.dependency_overrides[auth.require_admin] = lambda: None
    app.dependency_overrides[auth.db] = lambda: None
    return TestClient(app)


def test_the_administrator_reads_every_account_s_conversations(ws, admin):
    ana = store.create(ws, ANA, "De Ana")
    store.create(ws, BEA, "De Bea")

    body = admin.get("/api/admin/workspaces/ws/tutor").json()

    assert sorted(row["title"] for row in body["conversations"]) == ["De Ana", "De Bea"]
    assert {a["id"] for a in body["authors"]} == {ANA, BEA}
    detail = admin.get(f"/api/admin/workspaces/ws/tutor/{ANA}/{ana['id']}").json()
    assert detail["turns"][0]["text"] == "De Ana" and detail["author"]["username"] == "ana"
    assert admin.get(f"/api/admin/workspaces/ws/tutor/{BEA}/{ana['id']}").status_code == 404
    assert admin.get("/api/admin/workspaces/otra/tutor").status_code == 404


def test_no_fixed_route_of_the_tutor_sits_below_a_wildcard():
    from tests.evaluation.test_route_order import _wildcard_shadows

    assert _wildcard_shadows(router_module.router) == []
    assert _wildcard_shadows(admin_module.router) == []


def test_a_turn_started_before_its_route_wrote_pending_waits_for_it(ws, monkeypatch):
    """A free lane starts a job at once; the route still holds the lock until `pending` is written."""
    import threading

    started = threading.Event()
    seen = {}

    def handler(job, control):
        started.set()
        with store.lock_for(ws, job.user_id, job.params["conversation"]):
            record = store.get(ws, job.user_id, job.params["conversation"])
        seen["pending"] = (record.get("pending") or {}).get("job_id")
        seen["job"] = job.id

    fresh = JobRunner(EventBus(), {jobs.TURN: handler, jobs.CRITERIA: handler})
    monkeypatch.setattr(singletons, "runner", fresh)
    monkeypatch.setattr(router_module.inference, "is_available", lambda: True)
    monkeypatch.setattr(router_module, "_chain_error", lambda access: None)
    fresh.start()
    try:
        opened(ws)
        assert started.wait(5)
        for _ in range(50):
            if "pending" in seen:
                break
            threading.Event().wait(0.1)
    finally:
        fresh.shutdown()
    assert seen["pending"] == seen["job"]


def test_the_generic_job_route_does_not_take_the_tutor_s_jobs():
    from fastapi import FastAPI as App

    from server.jobs.catalogue import JOB_LABELS
    from tutor.api import install

    install(App())

    assert jobs.TURN not in JOB_LABELS and jobs.CRITERIA not in JOB_LABELS


def test_a_student_opens_the_notes_a_reply_cites_and_nothing_outside_them(ws, runner, monkeypatch):
    viewer = client(ws, role="viewer")
    monkeypatch.setattr(router_module.entrypoints, "load_concept_sources", lambda ws: {})
    monkeypatch.setattr(
        router_module,
        "read_document",
        lambda ws, sources, name: [{"location": "Tema 1", "text": "Texto."}] if name == "apuntes.pdf" else None,
    )

    found = viewer.get("/api/tutor/notes", params={"document": "apuntes.pdf"})
    assert found.status_code == 200 and found.json()["sections"][0]["location"] == "Tema 1"
    assert viewer.get("/api/tutor/notes", params={"document": "otro.pdf"}).status_code == 404


def test_a_message_carries_the_concept_the_student_chose_on_its_turn_and_never_on_its_job(ws, runner):
    response = client(ws).post(
        "/api/tutor/conversations", json={"message": "Explícamelo", "concept": "Recursividad"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["conversation"]["turns"][0]["concept"] == "Recursividad"
    assert "Recursividad" not in json.dumps(body["job"]["params"]), "a job's parameters are public"


def test_a_concept_the_syllabus_does_not_offer_is_refused(ws, runner):
    for name in ("No existe", "Notación asintótica"):
        refused = client(ws).post("/api/tutor/conversations", json={"message": "Hola", "concept": name})
        assert refused.status_code == 422, name
    assert store.list_for(ws, ANA) == []


def test_a_student_reads_the_units_and_the_concepts_to_choose_from(ws, runner):
    units = client(ws, role="viewer").get("/api/tutor/syllabus").json()["units"]

    assert units == [
        {"name": "Fundamentos", "concepts": ["Variable", "Función"]},
        {"name": "Avanzado", "concepts": ["Recursividad", "Memoización"]},
    ], "in the syllabus's order, without the generic concept"
