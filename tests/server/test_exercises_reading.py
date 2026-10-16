"""The bank as the class reads it: what a teacher showed, cut to it, and to whom.

A student reads the exercises shown to the whole class and the ones shown to their group,
each cut to the fields a teacher chose, with its type, level and concepts — never where it
comes from, who added it or the tagger's trace. A teacher reads the ones shown to anybody.
A group deleted takes with it what it alone saw.
"""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import auth, bank_marks, groups
from server.auth import queries
from server.auth.deps import Access
from server.db import mirror, repository
from server.db.models import OWNER, VIEWER, Base
from server.editors import bank_edit
from server.routers import bank as bank_routes
from server.routers import exercises as exercise_routes
from server.routers import members as member_routes
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


def _item(text: str, **extra) -> dict:
    return {
        "enunciado": text,
        "solucion": "la solución",
        "pista": "una pista",
        "nivel_dificultad": "basico",
        "concepts": ["Listas", "Bucles"],
        "primary_concept": "Listas",
        "source": "tema1.pdf",
        "_tagging": {"candidates": []},
        **extra,
    }


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(queries, "now", datetime.now)
    yield session
    session.close()


@pytest.fixture
def aula(db, tmp_path, monkeypatch):
    """A subject with a bank of three exercises, its owner and two students."""
    monkeypatch.setattr(mirror, "mirror_file", lambda ws, path: None)
    monkeypatch.setattr(bank_routes, "pipeline_payload", lambda access: {})
    workspace = repository.ensure_workspace(db, "aula", "Aula")
    people = {}
    for username, role in (("ana", OWNER), ("sara", VIEWER), ("diego", VIEWER)):
        user = queries.create_user(
            db, username=username, name=username, password_hash="x",
            evaluator_profile="teacher" if role == OWNER else "student",
        )
        queries.grant(db, workspace.id, user.id, role)
        people[username] = user
    db.flush()
    ws = Workspace(tmp_path / "aula", "aula")
    ws.artifacts_dir.mkdir(parents=True)
    ws.exemplars_profile_path.write_text(json.dumps(PROFILE), encoding="utf-8")
    ws.kg_path.write_text(json.dumps(GRAPH), encoding="utf-8")
    ws.exemplars_bank_path.write_text(
        json.dumps({
            "C001": _item("Recorre la lista"),
            "C002": _item("Suma dos números", nivel_dificultad="avanzado"),
            "C003": _item("Invierte la lista"),
        }),
        encoding="utf-8",
    )
    return SimpleNamespace(workspace=workspace, ws=ws, **people)


def client(db, aula, user, role) -> TestClient:
    access = Access(user=user, workspace=aula.workspace, role=role, ws=aula.ws)
    app = FastAPI()
    app.include_router(bank_routes.router)
    app.include_router(exercise_routes.router)
    app.dependency_overrides[auth.EDIT.dependency] = lambda: access
    app.dependency_overrides[auth.VIEW.dependency] = lambda: access
    app.dependency_overrides[auth.db] = lambda: db
    return TestClient(app)


def teacher(db, aula) -> TestClient:
    return client(db, aula, aula.ana, OWNER)


def reads(db, aula, user, **params) -> dict[str, dict]:
    answer = client(db, aula, user, VIEWER).get("/api/exercises", params=params)
    assert answer.status_code == 200, answer.text
    return {row["id"]: row for row in answer.json()["items"]}


def show(db, aula, items, **body):
    answer = teacher(db, aula).put("/api/bank/visibility", json={"items": items, **body})
    assert answer.status_code == 200, answer.text


# WHAT A STUDENT READS --------------------------------------------------------------------------


def test_nothing_is_read_until_a_teacher_shows_it(db, aula):
    assert reads(db, aula, aula.sara) == {}


def test_an_exercise_is_cut_to_what_was_shown_and_never_says_where_it_comes_from(db, aula):
    show(db, aula, ["C001"], level="full")
    show(db, aula, ["C002"], level="fields", fields=["pista"])

    read = reads(db, aula, aula.sara)

    assert read["C001"]["shown"] == ["enunciado", "solucion", "pista"]
    assert read["C001"]["solucion"] == "la solución"
    assert read["C002"]["shown"] == ["enunciado", "pista"]
    assert "solucion" not in read["C002"]
    assert read["C002"]["nivel_dificultad"] == "avanzado", "the level is always read"
    for row in read.values():
        assert row["concepts"] == ["Listas", "Bucles"] and row["primary_concept"] == "Listas"
        assert row["item_type"] == "ejercicio"
        assert not {"source", "origin", "added_by", "added_at", "_tagging", "key", "visibility"} & set(row)


def test_the_types_and_levels_are_counted_over_what_is_shown_alone(db, aula):
    show(db, aula, ["C002"], level="full")

    answer = client(db, aula, aula.sara, VIEWER).get("/api/exercises").json()

    assert answer["total"] == 1
    assert [(t["key"], t["count"]) for t in answer["item_types"]] == [("ejercicio", 1)]
    assert {d["value"]: d["count"] for d in answer["difficulties"]} == {"basico": 0, "avanzado": 1}


def test_the_filters_are_search_type_level_and_concept(db, aula):
    show(db, aula, ["C001", "C002", "C003"], level="full")

    answer = client(db, aula, aula.sara, VIEWER).get("/api/exercises").json()
    assert answer["concepts"] == [
        {"name": "Bucles", "unit": "Fundamentos"},
        {"name": "Listas", "unit": "Fundamentos"},
    ], "the concepts carried, in the syllabus' order"
    assert set(reads(db, aula, aula.sara, q="lista")) == {"C001", "C003"}
    assert set(reads(db, aula, aula.sara, difficulty="avanzado")) == {"C002"}
    assert set(reads(db, aula, aula.sara, concept="Bucles")) == {"C001", "C002", "C003"}
    assert reads(db, aula, aula.sara, item_type="otro") == {}


def test_a_subject_with_no_bank_reads_as_nothing_shown(db, aula):
    aula.ws.exemplars_bank_path.unlink()

    answer = client(db, aula, aula.sara, VIEWER).get("/api/exercises")

    assert answer.status_code == 200
    assert answer.json()["items"] == [] and answer.json()["total"] == 0


def test_one_exercise_is_read_only_when_shown(db, aula):
    show(db, aula, ["C001"], level="fields", fields=[])

    read = client(db, aula, aula.sara, VIEWER).get("/api/exercises/C001")
    hidden = client(db, aula, aula.sara, VIEWER).get("/api/exercises/C002")

    assert read.status_code == 200 and read.json()["item"]["shown"] == ["enunciado"]
    assert hidden.status_code == 404


# BY GROUP --------------------------------------------------------------------------------------


def test_an_exercise_shown_to_a_group_is_read_by_its_students_alone(db, aula):
    group = groups.create(db, aula.workspace, "Grupo A", aula.ana)
    groups.place(db, aula.workspace, aula.sara, group)
    show(db, aula, ["C001"], level="full", groups=[group.id])
    show(db, aula, ["C002"], level="full")

    assert set(reads(db, aula, aula.sara)) == {"C001", "C002"}
    assert set(reads(db, aula, aula.diego)) == {"C002"}
    teachers = teacher(db, aula).get("/api/exercises").json()["items"]
    assert {row["id"] for row in teachers} == {"C001", "C002"}, "a teacher reads every group's"


def test_the_teacher_s_listing_names_the_groups_that_see_an_exercise(db, aula):
    group = groups.create(db, aula.workspace, "Grupo A", aula.ana)
    show(db, aula, ["C001"], level="full", groups=[group.id])
    show(db, aula, ["C002"], level="full")

    items = {row["id"]: row for row in teacher(db, aula).get("/api/bank").json()["items"]}

    assert items["C001"]["visibility"]["groups"] == [group.id]
    assert items["C002"]["visibility"]["groups"] is None


def test_a_choice_of_groups_must_name_this_class_s_groups(db, aula):
    empty = teacher(db, aula).put(
        "/api/bank/visibility", json={"items": ["C001"], "level": "full", "groups": []}
    )
    unknown = teacher(db, aula).put(
        "/api/bank/visibility", json={"items": ["C001"], "level": "full", "groups": [999]}
    )

    assert empty.status_code == 422
    assert unknown.status_code == 404
    assert bank_marks.visibility(aula.ws) == {}, "a refused choice writes nothing"


def test_a_deleted_group_takes_what_it_alone_saw(db, aula):
    first = groups.create(db, aula.workspace, "Grupo A", aula.ana)
    second = groups.create(db, aula.workspace, "Grupo B", aula.ana)
    show(db, aula, ["C001"], level="full", groups=[first.id])
    show(db, aula, ["C002"], level="full", groups=[first.id, second.id])
    access = SimpleNamespace(user=aula.ana, workspace=aula.workspace, role=OWNER, ws=aula.ws)

    member_routes.delete_group(first.id, access=access, db=db)

    marks = bank_marks.visibility(aula.ws)
    named = bank_marks.keys(bank_edit._profile(aula.ws), json.loads(aula.ws.exemplars_bank_path.read_text()))
    assert named["C001"] not in marks
    assert marks[named["C002"]]["groups"] == [second.id]
