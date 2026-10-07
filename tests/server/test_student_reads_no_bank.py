"""A student reads their own exercise whole, and nothing of the bank it was made from.

The accepted attempt's prompt quotes the chosen exemplars with their solutions, and the
record's `resolved.few_shot` keeps their bodies; a revealed comparison card carries the
prompt and the raw answer of its arm. None of it reaches an account whose role in the
subject is `viewer`. The file and the session row keep all of it — the administrator reads
them from the panel — and a teacher still reads it here.
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from evaluation import EvaluationSession
from evaluation.api import router as evaluation_router
from server import auth
from server import generations as store
from server.auth.deps import Access
from server.routers.generations import router as generations_router
from variatio.core.workspace import Workspace

ANA = 1
BANK = "SOLUCIÓN DEL EJEMPLO DEL BANCO"


@pytest.fixture
def ws(tmp_path):
    ws = Workspace(tmp_path / "ws", slug="ws")
    store.save(
        ws,
        ANA,
        "job1",
        1,
        {
            "commission": {"concepts": ["Bucles"], "think": "low"},
            "resolved": {
                "item_type": "ejercicio",
                "targets": ["Bucles"],
                "few_shot": [{"id": "C001", "item": {"enunciado": BANK}, "origin": "target"}],
            },
            "prompt": f"Ejemplo 1: {BANK}",
            "output": {
                "item": {"enunciado": "Suma los pares", "solucion": "for i in ..."},
                "thinking": "pensado",
            },
        },
    )
    return ws


def _client(ws, role: str) -> TestClient:
    access = Access(
        user=SimpleNamespace(id=ANA, name="Ana", username="ana"),
        workspace=SimpleNamespace(id=1, slug="ws", name="WS"),
        role=role,
        ws=ws,
    )
    app = FastAPI()
    app.include_router(generations_router)
    app.dependency_overrides[auth.VIEW.dependency] = lambda: access
    app.dependency_overrides[auth.EDIT.dependency] = lambda: access
    return TestClient(app)


def _detail(ws, role: str) -> dict:
    [record], _ = store.list_for(ws, ANA)
    return _client(ws, role).get(f"/api/generations/{record['id']}").json()["generation"]


def test_a_student_reads_the_exercise_whole_with_its_solution(ws):
    generation = _detail(ws, "viewer")

    assert generation["item"] == {"enunciado": "Suma los pares", "solucion": "for i in ..."}
    assert generation["thinking"] == "pensado"


def test_a_student_reads_neither_the_prompt_nor_the_exemplars(ws):
    provenance = _detail(ws, "viewer")["provenance"]

    assert provenance["prompt"] is None
    assert provenance["resolved"]["few_shot"] == [{"id": "C001", "origin": "target"}]
    assert BANK not in str(provenance)


def test_the_listing_never_carried_the_bank(ws):
    body = _client(ws, "viewer").get("/api/generations").json()

    assert BANK not in str(body)


def test_a_teacher_still_reads_how_it_was_made(ws):
    provenance = _detail(ws, "editor")["provenance"]

    assert provenance["prompt"] == f"Ejemplo 1: {BANK}"
    assert provenance["resolved"]["few_shot"][0]["item"] == {"enunciado": BANK}


def test_the_file_keeps_everything(ws):
    _detail(ws, "viewer")
    [record], _ = store.list_for(ws, ANA)

    assert record["prompt"] == f"Ejemplo 1: {BANK}"


# A REVEALED COMPARISON -----------------------------------------------------------------------


def _arm(name: str) -> dict:
    return {
        "arm": name,
        "status": "ok",
        "item": {"enunciado": f"el de {name}"},
        "raw_response": f"respuesta cruda de {name}",
        "prompt": f"prompt de {name} con {BANK}",
        "model": "modelo",
        "provider": "local",
        "exemplar_ids": ["C001"],
        "elapsed_ms": 1200,
        "error": None,
        "checks": None,
        "retried": 0,
    }


REVEALED = {
    "id": "sesion000001",
    "created_at": 1787000000.0,
    "job_id": "job1",
    "set_id": "sesion000001",
    "assigned_by": None,
    "concepts": ["Recursividad"],
    "item_type": "ejercicio",
    "fixed": {},
    "curriculum": [],
    "instructions": "",
    "seed": 42,
    "shuffle": ["naive", "system"],
    "think": False,
    "arms": {name: _arm(name) for name in ("naive", "system")},
    "triage": {},
    "choice": 2,
    "choice_arm": "system",
    "chosen_at": 1787000100.0,
    "opened_at": None,
    "declined_at": None,
    "evaluator_note": None,
    "rating": None,
}


def _positions(role: str) -> list[dict]:
    access = SimpleNamespace(role=role)
    return evaluation_router._payload(EvaluationSession.from_dict(REVEALED), access)["positions"]


def test_a_students_revealed_cards_carry_no_trace():
    for card in _positions("viewer"):
        assert card["prompt"] is None
        assert card["raw_response"] is None
        assert card["item"]["enunciado"].startswith("el de ")
        assert card["arm"] in ("naive", "system")


def test_a_teachers_revealed_cards_keep_their_trace():
    for card in _positions("editor"):
        assert BANK in card["prompt"]
        assert card["raw_response"].startswith("respuesta cruda")
