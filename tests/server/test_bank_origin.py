"""Where each exercise of the bank comes from, a teacher's own exercises, and their tagging.

Collected from the documents (`C###`), written by a teacher (`M###`, «Manual») or a generated
exercise passed into the bank (`G###`): the origin is a field since 2026-10-14, and an older
exercise is read by its id. A teacher's exercise may be tagged by the system in the same
press (`tag_item`), whose concepts are merged into the bank as it is when they arrive.
"""

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import auth
from server.auth.deps import Access
from server.core import process
from server.db import mirror
from server.db.models import Base, User
from server.editors import bank_edit
from server.editors.bank_edit import BankError
from server.jobs import catalogue, lanes
from server.jobs.bus import EventBus
from server.jobs.catalogue import Job
from server.jobs.runner import JobRunner
from server.pipeline import approvals
from server.pipeline import jobs as handlers
from server.routers import bank as bank_routes
from variatio.core.workspace import Workspace

PROFILE = {
    "item_types": {
        "ejercicio": {
            "label": "Ejercicio de programación",
            "description": "El alumno escribe código.",
            "primary_field": "enunciado",
            "embed_fields": ["enunciado"],
            "general_generation_rules": ["El enunciado especifica la entrada y la salida."],
            "fields": {
                "enunciado": {"schema": {"type": "string"}, "description": "El texto."},
            },
        },
    }
}

GRAPH = {
    "concepts_by_domains": {"Fundamentos": ["Bucles", "Listas"]},
    "generic_non_taggable_concepts": [],
    "taggability_reviewed": True,
    "relations": [],
}

ANA = 7


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(mirror, "mirror_file", lambda ws, path: None)
    workspace = Workspace(tmp_path, "aula")
    workspace.artifacts_dir.mkdir(parents=True)
    _write(workspace.exemplars_profile_path, PROFILE)
    _write(workspace.kg_path, GRAPH)
    _write(
        workspace.exemplars_bank_path,
        {
            "C001": {"enunciado": "uno", "source": "tema1.pdf", "concepts": ["Bucles"]},
            # Promoted before the field existed: read by its id.
            "G001": {"enunciado": "dos", "source": "Variante promovida", "concepts": ["Listas"]},
        },
    )
    return workspace


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _bank(ws) -> dict:
    return json.loads(ws.exemplars_bank_path.read_text(encoding="utf-8"))


# THE ORIGIN --------------------------------------------------------------------------------------


def test_an_exercise_without_the_field_is_read_by_its_id(ws):
    rows = {row["id"]: row for row in bank_edit.listing(ws)["items"]}
    assert rows["C001"]["origin"] == bank_edit.EXTRACTED
    assert rows["G001"]["origin"] == bank_edit.GENERATED


def test_the_listing_counts_each_origin_and_names_only_the_documents(ws):
    bank_edit.add_item(ws, {"enunciado": "tres"}, "ejercicio", [], origin=bank_edit.MANUAL)
    listing = bank_edit.listing(ws)
    assert listing["origins"] == {"extracted": 1, "manual": 1, "generated": 1}
    assert listing["sources"] == ["tema1.pdf"]


def test_the_listing_filters_by_origin(ws):
    bank_edit.add_item(ws, {"enunciado": "tres"}, "ejercicio", [], origin=bank_edit.MANUAL)
    assert [row["id"] for row in bank_edit.listing(ws, origin="manual")["items"]] == ["M001"]
    assert [row["id"] for row in bank_edit.listing(ws, origin="generated")["items"]] == ["G001"]


# A TEACHER'S OWN EXERCISE -----------------------------------------------------------------------


def test_a_teachers_exercise_is_manual_with_who_and_when(ws):
    result = bank_edit.add_item(
        ws, {"enunciado": "tres"}, "ejercicio", ["Bucles"], "Bucles",
        origin=bank_edit.MANUAL, added_by=ANA,
    )
    assert result["item"]["id"] == "M001"
    stored = _bank(ws)["M001"]
    assert stored["origin"] == "manual" and stored["added_by"] == ANA
    assert stored["added_at"].startswith("20")
    assert stored["concepts"] == ["Bucles"] and stored["_tagging"] == {"method": "manual"}
    assert "source" not in stored


def test_ids_of_each_origin_count_apart(ws):
    for _ in range(2):
        bank_edit.add_item(ws, {"enunciado": "x"}, "ejercicio", [], origin=bank_edit.MANUAL)
    bank_edit.add_item(ws, {"enunciado": "y"}, "ejercicio", [], origin=bank_edit.GENERATED)
    assert set(_bank(ws)) == {"C001", "G001", "M001", "M002", "G002"}


def test_a_teacher_names_no_concept_the_graph_does_not_hold(ws):
    with pytest.raises(BankError):
        bank_edit.add_item(ws, {"enunciado": "x"}, "ejercicio", ["Inventado"], origin=bank_edit.MANUAL)
    with pytest.raises(BankError):
        bank_edit.add_item(
            ws, {"enunciado": "x"}, "ejercicio", ["Bucles"], "Listas", origin=bank_edit.MANUAL
        )
    assert set(_bank(ws)) == {"C001", "G001"}


def test_an_exercise_left_to_the_tagger_waits_untagged(ws):
    bank_edit.add_item(ws, {"enunciado": "x"}, "ejercicio", [], origin=bank_edit.MANUAL)
    stored = _bank(ws)["M001"]
    assert stored["concepts"] == [] and "_tagging" not in stored


# THE TAGGER'S CONCEPTS ARE MERGED, NEVER THE BANK IT READ ---------------------------------------


def test_the_tags_merge_into_the_bank_as_it_is_now(ws):
    bank_edit.add_item(ws, {"enunciado": "x"}, "ejercicio", [], origin=bank_edit.MANUAL)
    # Written while the tagger worked on M001.
    bank_edit.add_item(ws, {"enunciado": "y"}, "ejercicio", [], origin=bank_edit.MANUAL)
    bank_edit.delete_item(ws, "C001")

    result = bank_edit.apply_tags(
        ws,
        {
            "M001": {"concepts": ["Listas"], "primary_concept": "Listas", "_tagging": {"method": "llm"}},
            "C001": {"concepts": ["Bucles"], "primary_concept": "Bucles"},
        },
    )

    bank = _bank(ws)
    assert result["written"] == ["M001"]
    assert set(bank) == {"G001", "M001", "M002"}
    assert bank["M001"]["concepts"] == ["Listas"] and bank["M001"]["_tagging"] == {"method": "llm"}
    assert bank["M001"]["enunciado"] == "x"


def test_tagging_a_closed_banks_exercise_keeps_it_closed(ws):
    review = approvals.Approvals(ws)
    for artifact in approvals.ARTIFACTS:
        review.approve(artifact)
    bank_edit.apply_tags(ws, {"C001": {"concepts": ["Listas"], "primary_concept": "Listas"}})
    assert approvals.Approvals(ws).generation_unlocked()


def test_the_job_tags_what_it_was_asked_and_merges_it(ws, monkeypatch):
    seen = {}

    class Tagger:
        def tag_all(self, bank, ids):
            seen["ids"] = ids
            return {**bank, **{i: {**bank[i], "concepts": ["Bucles"], "primary_concept": "Bucles"} for i in ids}}

    bank_edit.add_item(ws, {"enunciado": "x"}, "ejercicio", [], origin=bank_edit.MANUAL)
    context = SimpleNamespace(exemplars_bank=_bank(ws), tagger=Tagger())
    monkeypatch.setattr(handlers.contexts, "require_inference", lambda: None)
    monkeypatch.setattr(handlers, "context_for", lambda job: context)
    monkeypatch.setattr(handlers, "_workspace", lambda job: ws)

    job = Job(kind=catalogue.TAG_ITEM, params={"items": ["M001", "M404"]}, workspace="aula")
    handlers.install()  # the construction's kinds join `HANDLERS` when the app is made
    result = handlers.HANDLERS[catalogue.TAG_ITEM](job, None)

    assert seen["ids"] == ["M001"]
    assert result == {"items": ["M001", "M404"], "tagged": ["M001"], "untagged": []}
    assert _bank(ws)["M001"]["concepts"] == ["Bucles"]


def test_tagging_one_exercise_is_its_authors_and_watched_by_them():
    assert catalogue.TAG_ITEM in catalogue.PRIVATE_KINDS
    assert catalogue.JOB_CLASS[catalogue.TAG_ITEM] == catalogue.BATCH
    assert catalogue.TAG_ITEM not in catalogue.JOB_ARTIFACT
    assert catalogue.TAG_ITEM not in catalogue.JOB_LABELS


# THE ROUTES ---------------------------------------------------------------------------------------


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(User(id=ANA, username="ana", name="Ana Pérez", password_hash="x"))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def queue(monkeypatch):
    monkeypatch.setattr(lanes, "backends_for", lambda kind, params=None: frozenset({lanes.LOCAL}))
    runner = JobRunner(EventBus(buffer_size=50), {catalogue.TAG_ITEM: lambda job, control: {}})
    monkeypatch.setattr(process, "runner", runner)
    monkeypatch.setattr(bank_routes.inference, "is_available", lambda: True)
    return runner


def _client(ws, db) -> TestClient:
    access = Access(
        user=SimpleNamespace(id=ANA, name="Ana Pérez", username="ana"),
        workspace=SimpleNamespace(id=1, slug="aula", name="Aula"),
        role="editor",
        ws=ws,
    )
    app = FastAPI()
    app.include_router(bank_routes.router)
    app.dependency_overrides[auth.EDIT.dependency] = lambda: access
    app.dependency_overrides[auth.db] = lambda: db
    return TestClient(app)


def _open_the_gates(ws):
    review = approvals.Approvals(ws)
    review.approve(approvals.KNOWLEDGE_GRAPH)
    review.approve(approvals.EXEMPLARS_PROFILE)


def test_the_listing_names_who_added_an_exercise(ws, db, monkeypatch):
    monkeypatch.setattr(bank_routes, "pipeline_payload", lambda access: {})
    bank_edit.add_item(ws, {"enunciado": "x"}, "ejercicio", [], origin=bank_edit.MANUAL, added_by=ANA)
    rows = {row["id"]: row for row in _client(ws, db).get("/api/bank").json()["items"]}
    assert rows["M001"]["added_by"] == {"id": ANA, "name": "Ana Pérez", "username": "ana"}
    assert "added_by" not in rows["C001"]


def test_adding_with_the_tagger_queues_it_on_the_new_exercise(ws, db, queue, monkeypatch):
    monkeypatch.setattr(bank_routes, "pipeline_payload", lambda access: {})
    _open_the_gates(ws)
    answer = _client(ws, db).post(
        "/api/bank", json={"item_type": "ejercicio", "fields": {"enunciado": "x"}, "tag": "auto"}
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["item"]["id"] == "M001" and body["item"]["concepts"] == []
    assert body["job"]["kind"] == catalogue.TAG_ITEM
    [job] = queue.pending("aula")
    assert job.params == {"items": ["M001"]} and job.user_id == ANA


def test_adding_with_the_tagger_behind_an_open_syllabus_writes_nothing(ws, db, queue, monkeypatch):
    monkeypatch.setattr(bank_routes, "pipeline_payload", lambda access: {})
    answer = _client(ws, db).post(
        "/api/bank", json={"item_type": "ejercicio", "fields": {"enunciado": "x"}, "tag": "auto"}
    )
    assert answer.status_code == 409
    assert set(_bank(ws)) == {"C001", "G001"}
    assert queue.pending("aula") == []


def test_adding_with_ones_own_concepts_queues_nothing(ws, db, queue, monkeypatch):
    monkeypatch.setattr(bank_routes, "pipeline_payload", lambda access: {})
    answer = _client(ws, db).post(
        "/api/bank",
        json={"fields": {"enunciado": "x"}, "tag": "manual", "concepts": ["Listas"]},
    )
    assert answer.status_code == 200
    assert answer.json()["job"] is None
    assert _bank(ws)["M001"]["concepts"] == ["Listas"]


def test_tagging_again_names_only_exercises_of_the_bank(ws, db, queue):
    _open_the_gates(ws)
    assert _client(ws, db).post("/api/bank/tag", json={"items": ["C404"]}).status_code == 404
    answer = _client(ws, db).post("/api/bank/tag", json={"items": ["C001"]})
    assert answer.status_code == 200
    assert answer.json()["job"]["params"] == {"items": ["C001"]}
