"""Who sees which exercise of the bank, a teacher's stars, and what a re-extraction keeps.

Marks are named by the exercise's CONTENT — its type and folded statement —, never by its id,
which a re-extraction renumbers; editing a statement carries them along. Every exercise is
hidden until a teacher shows it, whole or by fields, and the statement always goes. A star is
one teacher's. A re-extraction keeps what a person added, and puts aside what no longer fits.
"""

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import auth, bank_marks
from server.auth.deps import Access
from server.db import mirror
from server.db.models import Base, User, Workspace as WorkspaceRow
from server.editors import bank_edit
from server.routers import bank as bank_routes
from variatio.core.workspace import Workspace
from variatio.loaders.exemplars_profile import ExemplarsProfile

PROFILE = {
    "item_types": {
        "ejercicio": {
            "label": "Ejercicio",
            "primary_field": "enunciado",
            "embed_fields": ["enunciado"],
            "fields": {
                "enunciado": {"schema": {"type": "string"}, "description": "El texto."},
                "solucion": {"schema": {"type": "string"}, "description": "La solución."},
                "pista": {"schema": {"type": ["string", "null"]}, "description": "Una pista."},
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

ANA, LUIS = 1, 2


def _item(text: str, **extra) -> dict:
    return {"enunciado": text, "solucion": "s", "pista": None, "nivel_dificultad": "basico", **extra}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(mirror, "mirror_file", lambda ws, path: None)
    monkeypatch.setattr(bank_routes, "pipeline_payload", lambda access: {})
    workspace = Workspace(tmp_path, "aula")
    workspace.artifacts_dir.mkdir(parents=True)
    workspace.exemplars_profile_path.write_text(json.dumps(PROFILE), encoding="utf-8")
    workspace.kg_path.write_text(json.dumps(GRAPH), encoding="utf-8")
    workspace.exemplars_bank_path.write_text(
        json.dumps({"C001": _item("Recorre la lista"), "C002": _item("Suma dos números")}),
        encoding="utf-8",
    )
    return workspace


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add_all([
        User(id=ANA, username="ana", name="Ana", password_hash="x"),
        User(id=LUIS, username="luis", name="Luis", password_hash="x"),
        WorkspaceRow(id=1, slug="aula", name="Aula"),
    ])
    session.commit()
    yield session
    session.close()


def client(ws, db, user_id: int = ANA) -> TestClient:
    access = Access(
        user=SimpleNamespace(id=user_id, name="Ana", username="ana"),
        workspace=SimpleNamespace(id=1, slug="aula", name="Aula"),
        role="editor",
        ws=ws,
    )
    app = FastAPI()
    app.include_router(bank_routes.router)
    app.dependency_overrides[auth.EDIT.dependency] = lambda: access
    app.dependency_overrides[auth.db] = lambda: db
    return TestClient(app)


def rows(ws, db, user_id: int = ANA, **params) -> dict[str, dict]:
    answer = client(ws, db, user_id).get("/api/bank", params=params).json()
    return {row["id"]: row for row in answer["items"]}


def _profile(ws) -> ExemplarsProfile:
    return ExemplarsProfile(ws.exemplars_profile_path)


# THE KEY -----------------------------------------------------------------------------------------


def test_the_key_is_the_folded_statement_not_the_id(ws):
    profile = _profile(ws)
    key = bank_marks.fingerprint(profile, _item("Recorre  la LISTA"))
    assert key == bank_marks.fingerprint(profile, _item("recorre la lista"))
    assert key != bank_marks.fingerprint(profile, _item("Recorre la cola"))
    assert bank_marks.fingerprint(profile, _item("")) is None


# WHO SEES AN EXERCISE ---------------------------------------------------------------------------


def test_every_exercise_is_hidden_until_a_teacher_shows_it(ws, db):
    assert all(row["visibility"] is None for row in rows(ws, db).values())


def test_shown_whole_or_by_fields_never_without_the_statement_nor_the_level(ws, db):
    assert client(ws, db).put(
        "/api/bank/visibility", json={"items": ["C001"], "level": "full"}
    ).status_code == 200
    assert client(ws, db).put(
        "/api/bank/visibility",
        json={"items": ["C002"], "level": "fields", "fields": ["pista", "nivel_dificultad"]},
    ).status_code == 200

    shown = rows(ws, db)
    assert shown["C001"]["visibility"] == {
        "level": "full", "fields": ["enunciado", "solucion", "pista"], "groups": None,
    }
    assert shown["C002"]["visibility"] == {"level": "fields", "fields": ["enunciado", "pista"], "groups": None}
    assert list(rows(ws, db, visible=True)) == ["C001", "C002"]

    client(ws, db).put("/api/bank/visibility", json={"items": ["C001"], "level": "hidden"})
    assert list(rows(ws, db, visible=True)) == ["C002"]


def test_showing_an_exercise_does_not_reopen_a_closed_bank(ws, db):
    from server.pipeline import approvals

    review = approvals.Approvals(ws)
    for artifact in approvals.ARTIFACTS:
        review.approve(artifact)
    before = (ws.exemplars_bank_path).read_bytes()
    client(ws, db).put("/api/bank/visibility", json={"items": ["C001"], "level": "full"})
    assert ws.exemplars_bank_path.read_bytes() == before
    assert approvals.Approvals(ws).generation_unlocked()


def test_an_unknown_exercise_is_refused(ws, db):
    answer = client(ws, db).put("/api/bank/visibility", json={"items": ["C404"], "level": "full"})
    assert answer.status_code == 404


# THE STARS ---------------------------------------------------------------------------------------


def test_a_star_is_one_teachers_and_filters_their_list(ws, db):
    assert client(ws, db).put("/api/bank/C002/favourite").status_code == 200
    assert client(ws, db).put("/api/bank/C002/favourite").status_code == 200

    mine = client(ws, db).get("/api/bank").json()
    assert mine["marks"] == {"visible": 0, "favourites": 1, "extracted": 1}
    assert {row["id"]: row["favourite"] for row in mine["items"]} == {"C001": False, "C002": True}
    assert list(rows(ws, db, favourite=True)) == ["C002"]
    assert list(rows(ws, db, user_id=LUIS, favourite=True)) == []

    client(ws, db).delete("/api/bank/C002/favourite")
    assert list(rows(ws, db, favourite=True)) == []


# A STATEMENT REWRITTEN CARRIES ITS MARKS ---------------------------------------------------------


def test_editing_the_statement_carries_the_marks_along(ws, db):
    client(ws, db).put("/api/bank/visibility", json={"items": ["C001"], "level": "full"})
    client(ws, db).put("/api/bank/C001/favourite")
    client(ws, db, user_id=LUIS).put("/api/bank/C001/favourite")

    answer = client(ws, db).patch("/api/bank/C001", json={"fields": {"enunciado": "Recorre la lista dos veces"}})
    assert answer.status_code == 200, answer.text

    assert rows(ws, db)["C001"]["visibility"]["level"] == "full"
    assert rows(ws, db)["C001"]["favourite"] is True
    assert rows(ws, db, user_id=LUIS)["C001"]["favourite"] is True


def test_a_re_extraction_that_renumbers_keeps_the_marks_of_the_same_statement(ws, db):
    client(ws, db).put("/api/bank/visibility", json={"items": ["C002"], "level": "full"})
    ws.exemplars_bank_path.write_text(
        json.dumps({"C001": _item("Suma dos números"), "C002": _item("Algo nuevo")}), encoding="utf-8"
    )
    shown = rows(ws, db)
    assert shown["C001"]["visibility"]["level"] == "full"
    assert shown["C002"]["visibility"] is None


# WHAT A RE-EXTRACTION KEEPS ---------------------------------------------------------------------


def test_the_seed_keeps_what_a_person_added_and_puts_aside_what_no_longer_fits(ws):
    bank_edit.add_item(ws, _item("Mío y válido"), "ejercicio", [], origin=bank_edit.MANUAL, added_by=ANA)
    bank = json.loads(ws.exemplars_bank_path.read_text(encoding="utf-8"))
    bank["G001"] = {"item_type": "ejercicio", "enunciado": "Sin solución", "origin": "generated"}
    ws.exemplars_bank_path.write_text(json.dumps(bank), encoding="utf-8")

    kept, aside = bank_edit.seed(ws)

    assert list(kept) == ["M001"] and list(aside) == ["G001"]
    bank_edit.put_aside(ws, aside)
    [(key, entry)] = bank_edit.aside(ws).items()
    assert entry["id"] == "G001" and entry["item"]["enunciado"] == "Sin solución"


def test_an_exercise_put_aside_comes_back_as_it_was(ws, db):
    bank_edit.put_aside(
        ws, {"G007": {"enunciado": "Sin solución", "origin": "generated", "added_by": LUIS, "added_at": "2026-10-01T09:00:00+00:00"}}
    )
    [key] = list(bank_edit.aside(ws))
    listed = client(ws, db).get("/api/bank/set-aside").json()["items"]
    assert [entry["key"] for entry in listed] == [key]

    answer = client(ws, db).post(
        "/api/bank",
        json={"item_type": "ejercicio", "fields": _item("Con solución"), "tag": "manual", "concepts": ["Bucles"], "set_aside": key},
    )
    assert answer.status_code == 200, answer.text
    item = answer.json()["item"]
    assert item["id"] == "G001" and item["origin"] == "generated"
    assert item["added_by"] == LUIS and item["added_at"].startswith("2026-10-01")
    assert bank_edit.aside(ws) == {}


def test_two_exercises_with_one_statement_keep_their_marks_apart(ws, db):
    ws.exemplars_bank_path.write_text(
        json.dumps({"C001": _item("Recorre la lista"), "C002": _item("Recorre la lista", solucion="otra")}),
        encoding="utf-8",
    )
    client(ws, db).put("/api/bank/visibility", json={"items": ["C002"], "level": "full"})
    client(ws, db).put("/api/bank/C002/favourite")

    shown = rows(ws, db)
    assert shown["C001"]["visibility"] is None and shown["C001"]["favourite"] is False
    assert shown["C002"]["visibility"]["level"] == "full" and shown["C002"]["favourite"] is True
