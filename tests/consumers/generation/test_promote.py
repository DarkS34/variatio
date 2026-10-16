"""A teacher passes their own generated exercises into the bank, from the bank's page or theirs.

Each row says whether it is in the bank now and whether this account may pass it; passing
one may correct it first — the bank keeps the correction, the file keeps what the model
wrote — and may have the system tag it. A field the commission left out has to be written.
"""

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from consumers.generation.api.router import router as generations_router
from server import auth
from server import generations as store
from server.auth.deps import Access
from server.core import process
from server.db import mirror
from server.editors import bank_edit
from server.jobs import catalogue, lanes
from server.jobs.bus import EventBus
from server.jobs.runner import JobRunner
from server.pipeline import approvals
from server.routers import bank as bank_routes
from variatio.core.workspace import Workspace

PROFILE = {
    "item_types": {
        "ejercicio": {
            "label": "Ejercicio",
            "primary_field": "enunciado",
            "embed_fields": ["enunciado"],
            "fields": {
                "enunciado": {"schema": {"type": "string"}, "description": "El texto."},
                "solucion": {"schema": {"type": "string"}, "description": "La solución."},
                "nivel_dificultad": {"schema": {"enum": ["basico", "avanzado"]}},
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

ANA = 1


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(mirror, "mirror_file", lambda ws, path: None)
    monkeypatch.setattr("consumers.generation.api.router.pipeline_payload", lambda access: {})
    workspace = Workspace(tmp_path / "aula", slug="aula")
    workspace.artifacts_dir.mkdir(parents=True)
    workspace.exemplars_profile_path.write_text(json.dumps(PROFILE), encoding="utf-8")
    workspace.kg_path.write_text(json.dumps(GRAPH), encoding="utf-8")
    workspace.exemplars_bank_path.write_text(
        json.dumps({"C001": {"enunciado": "uno", "solucion": "s", "nivel_dificultad": "basico"}}),
        encoding="utf-8",
    )
    for index, (text, level, omit) in enumerate(
        (("recorre la lista", "basico", []), ("ordena la lista", "avanzado", ["solucion"])), 1
    ):
        item = {"enunciado": text, "nivel_dificultad": level}
        if not omit:
            item["solucion"] = "for x in lista: ..."
        store.save(
            workspace,
            ANA,
            "job",
            index,
            {
                "commission": {"concepts": ["Bucles"], "omit": omit},
                "resolved": {"item_type": "ejercicio", "targets": ["Bucles"]},
                "output": {"item": item},
            },
        )
    return workspace


def client(ws, role: str = "editor") -> TestClient:
    access = Access(
        user=SimpleNamespace(id=ANA, name="Ana", username="ana"),
        workspace=SimpleNamespace(id=1, slug="aula", name="Aula"),
        role=role,
        ws=ws,
    )
    app = FastAPI()
    app.include_router(generations_router)
    app.dependency_overrides[auth.VIEW.dependency] = lambda: access
    app.dependency_overrides[auth.EDIT.dependency] = lambda: access
    return TestClient(app)


def rows(ws, role: str = "editor", **params) -> dict[str, dict]:
    answer = client(ws, role).get("/api/generations", params=params).json()
    return {row["item"]["enunciado"]: row for row in answer["generations"]}


def id_of(ws, text: str) -> str:
    [record] = [r for r in store.list_for(ws, ANA, limit=50)[0] if store.item_of(r)["enunciado"] == text]
    return record["id"]


def _bank(ws) -> dict:
    return json.loads(ws.exemplars_bank_path.read_text(encoding="utf-8"))


def test_a_teachers_rows_say_they_may_be_passed_in(ws):
    row = rows(ws)["recorre la lista"]
    assert row["in_bank"] is None and row["promotable"] is True


def test_a_student_is_told_nothing_of_the_bank(ws):
    row = rows(ws, role="viewer")["recorre la lista"]
    assert row["in_bank"] is None and row["promotable"] is False


def test_passing_one_in_corrected_keeps_the_models_file(ws):
    generation = id_of(ws, "recorre la lista")
    answer = client(ws).post(
        f"/api/generations/{generation}/promote",
        json={"fields": {"enunciado": "recorre la lista dos veces", "solucion": "s", "nivel_dificultad": "basico"}},
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["item"]["id"] == "G001" and answer.json()["job"] is None
    stored = _bank(ws)["G001"]
    assert stored["enunciado"] == "recorre la lista dos veces"
    assert stored["origin"] == "generated" and stored["added_by"] == ANA
    assert stored["concepts"] == ["Bucles"]
    assert store.item_of(store.get(ws, ANA, generation))["enunciado"] == "recorre la lista"

    row = rows(ws)["recorre la lista"]
    assert row["in_bank"] == "G001" and row["promotable"] is False
    assert list(rows(ws, bank="in")) == ["recorre la lista"]
    assert list(rows(ws, bank="out")) == ["ordena la lista"]


def test_one_in_the_bank_is_refused_and_one_deleted_from_it_comes_back(ws):
    generation = id_of(ws, "recorre la lista")
    assert client(ws).post(f"/api/generations/{generation}/promote").status_code == 200
    assert client(ws).post(f"/api/generations/{generation}/promote").status_code == 409
    bank_edit.delete_item(ws, "G001")
    assert rows(ws)["recorre la lista"]["promotable"] is True


def test_a_field_left_out_has_to_be_written_to_pass_it_in(ws):
    generation = id_of(ws, "ordena la lista")
    assert client(ws).post(f"/api/generations/{generation}/promote").status_code == 422
    answer = client(ws).post(
        f"/api/generations/{generation}/promote",
        json={"fields": {"enunciado": "ordena la lista", "solucion": "sorted(lista)", "nivel_dificultad": "avanzado"}},
    )
    assert answer.status_code == 200


def test_the_level_filters_the_list(ws):
    assert list(rows(ws, difficulty="avanzado")) == ["ordena la lista"]


def test_passing_one_in_for_the_tagger_queues_it(ws, monkeypatch):
    review = approvals.Approvals(ws)
    review.approve(approvals.KNOWLEDGE_GRAPH)
    review.approve(approvals.EXEMPLARS_PROFILE)
    monkeypatch.setattr(lanes, "backends_for", lambda kind, params=None: frozenset({lanes.LOCAL}))
    runner = JobRunner(EventBus(buffer_size=50), {catalogue.TAG_ITEM: lambda job, control: {}})
    monkeypatch.setattr(process, "runner", runner)
    monkeypatch.setattr(bank_routes.inference, "is_available", lambda: True)

    generation = id_of(ws, "recorre la lista")
    answer = client(ws).post(f"/api/generations/{generation}/promote", json={"tag": "auto"})

    assert answer.status_code == 200, answer.text
    assert _bank(ws)["G001"]["concepts"] == []
    assert answer.json()["job"]["params"] == {"items": ["G001"]}
