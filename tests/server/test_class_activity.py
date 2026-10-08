"""What a class does, week by week, for its teachers: counted by code, summed up by the model.

The week is the unit (ISO, Monday to Sunday, UTC). A teacher reads what the students asked the
tutor and which exercises they generated — dates, kinds, concepts, levels, never a message or
a statement — of the class and of each student, a paused student marked and a removed one
gone. The words of what they ask are the weekly digest's: one call per concept, paraphrase
only, every theme checked for copied words and names, and counted from its references.
"""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import activity, curriculum
from server.db import identity, repository
from server.db.models import EDITOR, OWNER, VIEWER, Base
from server.routers import activity as activity_routes
from tutor.api import activity as tutor_activity
from tutor.api import digest as digest_job
from tutor.digest import Asked, clean_themes, names_someone
from tutor.turn import TurnResult
from variatio.core.workspace import Workspace
from variatio.loaders.knowledge_graph import KnowledgeGraph

from ..conftest import CHAIN_GRAPH

# Monday 5 October 2026 opens week 41; Sunday the 11th closes it.
WEEK = "2026-W41"
LAST_WEEK = "2026-W40"
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)

ANA = activity.Student(1, "Ana Ruiz", "ana", False)
LUIS = activity.Student(2, "Luis Gil", "luis", False)
MARTA = activity.Student(3, "Marta Sanz", "marta", True)
CLASS = [ANA, LUIS, MARTA]


@pytest.fixture(autouse=True)
def tutor_reader(monkeypatch):
    monkeypatch.setattr(activity, "TUTOR_READER", tutor_activity.read)
    activity._cache.clear()
    yield
    activity._cache.clear()


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(root=tmp_path / "aula", slug="aula")
    workspace.artifacts_dir.mkdir(parents=True, exist_ok=True)
    workspace.kg_path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    return workspace


def _graph(ws):
    return KnowledgeGraph(str(ws.kg_path))


def _exercise(ws, user_id, at, concepts, level="basico", item_type="ejercicio", number=0):
    generation_id = f"{at.strftime('%Y%m%dT%H%M%SZ')}-job{user_id}-{number}"
    path = ws.generations_dir / f"user_{user_id}" / f"{generation_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "format": 1,
        "id": generation_id,
        "created_at": at.isoformat().replace("+00:00", "Z"),
        "commission": {"item_type": item_type, "concepts": concepts},
        "resolved": {"item_type": item_type, "targets": concepts},
        "output": {"item": {"enunciado": "Un enunciado privado", "nivel_dificultad": level}},
    }
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return generation_id


def _conversation(ws, user_id, conversation_id, exchanges, opened_from=None):
    """Write a conversation: each exchange is (moment, text, kind, focus, sent_back, chosen)."""
    turns = []
    for moment, text, kind, focus, sent_back, chosen in exchanges:
        student = {"role": "student", "text": text, "at": moment.isoformat().replace("+00:00", "Z")}
        if chosen:
            student["concept"] = chosen
        turns.append(student)
        if kind is None:
            continue
        reply = {
            "role": "tutor",
            "text": "¿Qué crees tú?",
            "at": moment.isoformat().replace("+00:00", "Z"),
            "kind": kind,
            "card": {"concepts": [focus] if focus else []},
        }
        if sent_back:
            reply["sent_back"] = [focus, sent_back]
        turns.append(reply)
    record = {
        "format": 1,
        "id": conversation_id,
        "turns": turns,
        "opened_from": opened_from or {"kind": "message"},
    }
    path = ws.root / "tutor" / f"user_{user_id}" / f"{conversation_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return record


def at(day, hour=10, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


# THE WEEK -----------------------------------------------------------------------------------


def test_a_week_runs_from_monday_to_sunday_in_utc():
    assert activity.week_of(datetime(2026, 10, 11, 23, 59, tzinfo=timezone.utc)) == WEEK
    assert activity.week_of(datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)) == "2026-W42"
    assert activity.monday(WEEK).isoformat() == "2026-10-05"
    assert activity.previous_week("2026-W01") == "2025-W52"


def test_a_week_that_does_not_exist_is_refused():
    for wrong in ("2026-W54", "2026-41", "semana", "2026-W1"):
        with pytest.raises(ValueError):
            activity.parse_week(wrong)


def test_the_history_runs_from_the_first_active_week_and_keeps_an_empty_one(ws):
    _exercise(ws, ANA.id, datetime(2026, 9, 22, 9, tzinfo=timezone.utc), ["Variable"])
    _exercise(ws, ANA.id, at(6), ["Función"])
    scope = activity.read_scope(ws, CLASS)

    strip = activity.history(scope, set(), now=NOW)

    assert strip["current"] == WEEK
    assert [w["week"] for w in strip["weeks"]] == [WEEK, LAST_WEEK, "2026-W39"]
    assert [w["exercises"] for w in strip["weeks"]] == [1, 0, 1]


# WHAT A WEEK COUNTS -----------------------------------------------------------------------


def test_a_week_counts_messages_by_kind_concept_and_prerequisite(ws):
    _conversation(
        ws,
        ANA.id,
        "20261006T100000Z-aaaaaa",
        [
            (at(6), "¿Qué es la recursividad?", "theory", "Recursividad", "Función", None),
            (at(6, 11), "Hola", "social", None, None, None),
            (at(7), "Dame la solución", "solution", "Recursividad", None, None),
        ],
    )
    _conversation(
        ws,
        LUIS.id,
        "20261007T100000Z-bbbbbb",
        [(at(7), "No entiendo funciones", "theory", "Función", None, "Función")],
    )
    scope = activity.read_scope(ws, CLASS)

    answer = activity.week(scope, WEEK, _graph(ws), now=NOW)
    tutor = answer["tutor"]

    assert tutor["messages"] == 4
    assert tutor["students"] == 2
    assert tutor["by_kind"] == {"theory": 2, "social": 1, "solution": 1}
    assert [(c["concept"], c["messages"], c["students"]) for c in tutor["by_concept"]] == [
        ("Función", 1, 1),
        ("Recursividad", 2, 1),
    ]
    assert tutor["sent_back"] == [
        {"concept": "Recursividad", "prerequisite": "Función", "times": 1, "students": 1}
    ]
    assert tutor["per_day"] == [0, 2, 2, 0, 0, 0, 0]


def test_an_older_turn_tells_its_send_back_through_its_map(ws):
    record = _conversation(
        ws, ANA.id, "20261006T100000Z-cccccc", [(at(6), "Recursividad", "theory", "Recursividad", None, None)]
    )
    record["turns"][1]["concept_map"] = {"concept": "Recursividad", "review": "Función"}
    path = ws.root / "tutor" / f"user_{ANA.id}" / "20261006T100000Z-cccccc.json"
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    reading = tutor_activity.read(ws, [ANA.id])

    assert reading.messages[0].sent_back == "Función"


def test_a_week_counts_exercises_by_type_level_concept_and_unit(ws):
    taken = _exercise(ws, ANA.id, at(6), ["Recursividad"], level="avanzado")
    _exercise(ws, ANA.id, at(6, 11), ["Variable"], number=1)
    _exercise(ws, LUIS.id, at(8), ["Variable"], item_type="analisis")
    _conversation(
        ws,
        ANA.id,
        "20261006T120000Z-dddddd",
        [(at(6, 12), "Este ejercicio", "exercise", "Recursividad", None, None)],
        opened_from={"kind": "generation", "generation_id": taken},
    )
    scope = activity.read_scope(ws, CLASS)

    block = activity.week(scope, WEEK, _graph(ws), now=NOW)["exercises"]

    assert block["count"] == 3 and block["students"] == 2
    assert block["by_type"] == [
        {"type": "ejercicio", "count": 2, "levels": {"avanzado": 1, "basico": 1}},
        {"type": "analisis", "count": 1, "levels": {"basico": 1}},
    ]
    assert [(c["concept"], c["count"]) for c in block["by_concept"]] == [("Variable", 2), ("Recursividad", 1)]
    assert [(u["unit"], u["count"]) for u in block["by_unit"]] == [("Fundamentos", 2), ("Avanzado", 1)]
    assert block["to_tutor"] == 1


def test_a_removed_student_counts_for_nothing_and_a_paused_one_is_marked(ws):
    _exercise(ws, 99, at(6), ["Variable"])
    _exercise(ws, MARTA.id, at(6), ["Variable"])
    scope = activity.read_scope(ws, CLASS)

    answer = activity.week(scope, WEEK, _graph(ws), now=NOW)

    assert answer["exercises"]["count"] == 1
    marta = next(row for row in answer["students"] if row["id"] == MARTA.id)
    assert marta["disabled"] is True and marta["exercises"] == 1


def test_a_closed_week_does_not_move_when_a_conversation_goes_on(ws):
    exchange = [(at(6), "¿Qué es una variable?", "theory", "Variable", None, None)]
    _conversation(ws, ANA.id, "20261006T100000Z-eeeeee", exchange)
    before = activity.week(activity.read_scope(ws, CLASS), WEEK, _graph(ws), now=NOW)["tutor"]

    _conversation(
        ws,
        ANA.id,
        "20261006T100000Z-eeeeee",
        exchange + [(datetime(2026, 10, 13, tzinfo=timezone.utc), "Y ahora", "theory", "Variable", None, None)],
    )
    after = activity.week(activity.read_scope(ws, CLASS), WEEK, _graph(ws), now=NOW)["tutor"]

    assert after == before


def test_one_student_s_week_counts_them_alone_beside_the_class_median(ws):
    _exercise(ws, ANA.id, at(6), ["Variable"])
    _exercise(ws, ANA.id, at(7), ["Variable"], number=1)
    _exercise(ws, LUIS.id, at(7), ["Variable"])
    scope = activity.read_scope(ws, CLASS, LUIS)

    answer = activity.week(scope, WEEK, _graph(ws), now=NOW)

    assert answer["scope"] == "student" and answer["student"]["id"] == LUIS.id
    assert answer["exercises"]["count"] == 1
    assert answer["median"] == {"messages": 0, "exercises": 1.5}
    assert "students" not in answer


# WHAT MATTERS ------------------------------------------------------------------------------


def _askers(ws, count, concept="Recursividad", prerequisite="Función", kind="theory"):
    for user_id in range(10, 10 + count):
        _conversation(
            ws,
            user_id,
            f"20261006T10000{user_id % 10}Z-{user_id:06x}",
            [(at(6), f"duda {user_id}", kind, concept, prerequisite, None)],
        )
    return [activity.Student(i, f"Alumno {i}", f"a{i}", False) for i in range(10, 10 + count)]


def test_a_concept_many_ask_about_leads_with_its_prerequisite(ws):
    students = _askers(ws, 4) + [ANA]

    findings = activity.week(activity.read_scope(ws, students), WEEK, _graph(ws), now=NOW)["findings"]

    assert findings[0] == {
        "kind": "asked",
        "concept": "Recursividad",
        "students": 4,
        "of": 5,
        "prerequisite": "Función",
        "sent_back": 4,
        "area": "tutor",
    }
    assert {"kind": "idle", "students": 1, "of": 5, "open": True, "area": "tutor"} in findings


def test_two_students_asking_are_no_pattern(ws):
    students = _askers(ws, 2)

    findings = activity.week(activity.read_scope(ws, students), WEEK, _graph(ws), now=NOW)["findings"]

    assert all(f["kind"] != "asked" for f in findings)


def test_a_concept_where_they_ask_for_the_solution_is_said(ws):
    students = _askers(ws, 5, prerequisite=None, kind="solution")

    findings = activity.week(activity.read_scope(ws, students), WEEK, _graph(ws), now=NOW)["findings"]

    assert {
        "kind": "solutions",
        "concept": "Recursividad",
        "solution": 5,
        "messages": 5,
        "area": "tutor",
    } in findings


def test_a_unit_covered_in_class_and_not_practised_is_said(ws):
    _exercise(ws, ANA.id, at(6), ["Variable"])
    scope = activity.read_scope(ws, CLASS)

    findings = activity.week(
        scope, WEEK, _graph(ws), progress=["Variable", "Función", "Recursividad"], now=NOW
    )["findings"]

    assert {"kind": "unpractised", "units": ["Avanzado"], "more": 0, "area": "exercises"} in findings


def test_fewer_active_students_than_the_week_before_is_said(ws):
    _exercise(ws, ANA.id, datetime(2026, 9, 29, tzinfo=timezone.utc), ["Variable"])
    _exercise(ws, LUIS.id, datetime(2026, 9, 29, tzinfo=timezone.utc), ["Variable"])
    _exercise(ws, ANA.id, at(6), ["Variable"], number=1)

    findings = activity.week(activity.read_scope(ws, CLASS), WEEK, _graph(ws), now=NOW)["findings"]

    assert {"kind": "trend", "active": 1, "previous": 2, "open": True, "area": "exercises"} in findings


def test_each_area_counts_who_did_nothing_in_it_alone(ws):
    # Ana wrote to the tutor and generated nothing; Luis generated and never wrote. Each page
    # of the screen says who did nothing there, not who did nothing at all.
    _conversation(ws, ANA.id, "20261006T100000Z-0000aa", [(at(6), "duda", "theory", "Recursividad", None, None)])
    _exercise(ws, LUIS.id, at(6), ["Variable"])

    findings = activity.week(activity.read_scope(ws, CLASS), WEEK, _graph(ws), now=NOW)["findings"]

    idle = {f["area"]: f for f in findings if f["kind"] == "idle"}
    # Marta is paused: the active are Ana and Luis, and one of them did nothing in each area.
    assert (idle["tutor"]["students"], idle["tutor"]["of"]) == (1, 2)
    assert (idle["exercises"]["students"], idle["exercises"]["of"]) == (1, 2)


def test_a_student_who_did_nothing_has_one_finding_per_area(ws):
    findings = activity.week(activity.read_scope(ws, CLASS, LUIS), WEEK, _graph(ws), now=NOW)["findings"]

    assert findings == [
        {"kind": "quiet", "open": True, "area": "tutor"},
        {"kind": "quiet", "open": True, "area": "exercises"},
    ]


def test_a_row_counts_its_days_apart_for_each_page(ws):
    _conversation(ws, ANA.id, "20261006T100000Z-0000aa", [(at(6), "duda", "theory", "Recursividad", None, None)])
    _exercise(ws, ANA.id, at(7), ["Variable"])

    rows = activity.week(activity.read_scope(ws, CLASS), WEEK, _graph(ws), now=NOW)["students"]

    ana = next(row for row in rows if row["id"] == ANA.id)
    assert sum(ana["message_days"]) == 1 and sum(ana["exercise_days"]) == 1
    assert ana["days"] == [a + b for a, b in zip(ana["message_days"], ana["exercise_days"])]


# THE DIGEST -------------------------------------------------------------------------------


def test_the_checks_drop_a_copied_theme_a_named_one_and_an_empty_one():
    asked = [
        Asked("no entiendo por qué la función se llama a sí misma sin parar nunca", (1, "c", 0)),
        Asked("¿qué es el caso base exactamente?", (2, "d", 2)),
    ]
    answer = {
        "themes": [
            {"text": "Confunden el caso base con la llamada recursiva", "messages": [1, 2]},
            {"text": "no entiendo por qué la función se llama a sí misma sin parar", "messages": [1]},
            {"text": "Luis no ve el caso base", "messages": [2]},
            {"text": "Piden ejemplos", "messages": [7]},
        ]
    }

    kept, failures = clean_themes(answer, asked, ["Luis Gil", "luis"])

    assert kept == [
        {"text": "Confunden el caso base con la llamada recursiva", "refs": [[1, "c", 0], [2, "d", 2]]}
    ]
    assert failures == ["copy", "name", "empty"]


def test_a_name_is_found_whole_or_by_a_long_part_and_not_inside_a_word():
    assert names_someone("Marta pregunta por la pila", ["Marta Sanz"])
    assert names_someone("según SANZ no hay caso base", ["Marta Sanz"])
    assert not names_someone("Piden más ejemplos", ["Marta Sanz"])
    assert not names_someone("Confunden la martingala", ["Marta Sanz"])


def test_the_job_groups_the_week_reads_the_texts_and_writes_references(ws, monkeypatch):
    for user_id, text in ((ANA.id, "¿Caso base?"), (LUIS.id, "No paro de llamar")):
        _conversation(
            ws, user_id, f"20261006T10000{user_id}Z-{user_id:06x}", [(at(6), text, "theory", "Recursividad", None, None)]
        )
    _conversation(ws, ANA.id, "20261006T110000Z-000009", [(at(6, 11), "Hola", "social", None, None, None)])
    seen = {}

    def summarise(concept, unit, asked, **kwargs):
        seen[concept] = [item.text for item in asked]
        seen["names"] = kwargs["names"]
        return [{"text": "Confunden el caso base", "refs": [list(item.ref) for item in asked]}]

    monkeypatch.setattr(digest_job, "summarise", summarise)
    monkeypatch.setattr(digest_job.deps, "require_inference", lambda: None)
    monkeypatch.setattr(digest_job.installation, "workspace_for", lambda slug: ws)
    monkeypatch.setattr(
        digest_job.activity, "students_of", lambda session, workspace: [ANA, LUIS]
    )
    monkeypatch.setattr(
        digest_job.repository, "get_workspace", lambda session, slug: SimpleNamespace(id=1)
    )
    job = SimpleNamespace(workspace="aula", params={"week": WEEK})
    control = SimpleNamespace(emit=lambda kind, payload: None, should_cancel=lambda: False)

    result = digest_job.handle_digest(job, control)

    assert result == {"week": WEEK, "concepts": 1, "themes": 1}
    assert sorted(seen["Recursividad"]) == ["No paro de llamar", "¿Caso base?"]
    assert "Ana Ruiz" in seen["names"] and "luis" in seen["names"]
    stored = json.loads(activity.digest_path(ws, WEEK).read_text(encoding="utf-8"))
    assert stored["messages_seen"] == 2
    assert "Caso base?" not in json.dumps(stored, ensure_ascii=False)
    assert sorted(ref[0] for ref in stored["concepts"][0]["themes"][0]["refs"]) == [ANA.id, LUIS.id]


def test_a_digest_is_counted_over_the_class_and_cut_for_one_student(ws):
    digest = {
        "written_at": "2026-10-07T09:00:00Z",
        "messages_seen": 3,
        "concepts": [
            {
                "concept": "Recursividad",
                "unit": "Avanzado",
                "themes": [
                    {"text": "Confunden el caso base", "refs": [[ANA.id, "x", 0], [LUIS.id, "y", 0], [99, "z", 0]]},
                    {"text": "Piden la solución", "refs": [[LUIS.id, "y", 2]]},
                ],
            }
        ],
    }
    _conversation(ws, ANA.id, "20261008T100000Z-ffffff", [(at(8), "otra", "theory", "Recursividad", None, None)])

    whole = activity.week(activity.read_scope(ws, CLASS), WEEK, _graph(ws), digest=digest, now=NOW)["digest"]
    ana = activity.week(activity.read_scope(ws, CLASS, ANA), WEEK, _graph(ws), digest=digest, now=NOW)["digest"]

    assert [(t["messages"], t["students"]) for t in whole["concepts"][0]["themes"]] == [(2, 2), (1, 1)]
    assert whole["new_since"] == 1
    assert ana["concepts"][0]["themes"] == [
        {"text": "Confunden el caso base", "messages": 2, "students": 2, "mine": 1}
    ]


def test_a_reply_keeps_the_prerequisite_it_sent_the_student_back_to():
    result = TurnResult(text="Repasa funciones", kind="theory", decided_by="model", state={}, sent_back=("Recursividad", "Función"))

    assert result.record()["sent_back"] == ["Recursividad", "Función"]
    assert TurnResult(text="x", kind="social", decided_by="model", state={}).record()["sent_back"] is None


# THE ROUTES -------------------------------------------------------------------------------


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(identity, "now", datetime.now)
    yield session
    session.close()


@pytest.fixture
def aula(db, ws):
    workspace = repository.ensure_workspace(db, "aula", "Programación I")
    people = {}
    for username, role, profile in (("profe", OWNER, "teacher"), ("bea", EDITOR, "teacher"), ("sara", VIEWER, "student")):
        user = identity.create_user(db, username=username, name=username.title(), password_hash="x", evaluator_profile=profile)
        identity.grant(db, workspace.id, user.id, role)
        people[username] = user
    db.flush()
    teacher = SimpleNamespace(user=people["profe"], workspace=workspace, role=OWNER, ws=ws)
    return SimpleNamespace(workspace=workspace, teacher=teacher, **people)


def test_the_routes_read_the_class_of_the_subject_and_no_one_else(db, aula, ws, monkeypatch):
    monkeypatch.setattr(activity, "current_week", lambda now=None: WEEK)
    _exercise(ws, aula.sara.id, at(6), ["Variable"])
    _exercise(ws, aula.bea.id, at(6), ["Variable"])

    strip = activity_routes.weeks(student=None, access=aula.teacher, db=db)
    week = activity_routes.week(WEEK, student=aula.sara.id, access=aula.teacher, db=db)

    assert [s["username"] for s in strip["students"]] == ["sara"]
    assert strip["weeks"][0]["exercises"] == 1
    assert week["exercises"]["count"] == 1 and week["student"]["username"] == "sara"
    for wrong in (aula.bea.id, 9999):
        with pytest.raises(HTTPException) as refused:
            activity_routes.week(WEEK, student=wrong, access=aula.teacher, db=db)
        assert refused.value.status_code == 404


def test_a_future_or_malformed_week_does_not_exist(db, aula, monkeypatch):
    monkeypatch.setattr(activity, "current_week", lambda now=None: WEEK)

    for wrong in ("2026-W42", "ayer"):
        with pytest.raises(HTTPException) as refused:
            activity_routes.week(wrong, student=None, access=aula.teacher, db=db)
        assert refused.value.status_code == 404


def test_a_week_with_too_few_messages_is_not_summed_up(db, aula, ws, monkeypatch):
    monkeypatch.setattr(activity, "current_week", lambda now=None: WEEK)
    monkeypatch.setattr(activity_routes.singletons.runner, "handlers", {activity_routes.DIGEST_KIND: None})
    _conversation(ws, aula.sara.id, "20261006T100000Z-111111", [(at(6), "duda", "theory", "Variable", None, None)])

    with pytest.raises(HTTPException) as refused:
        activity_routes.write_digest(WEEK, access=aula.teacher, db=db)

    assert refused.value.status_code == 422


def test_one_digest_of_a_week_at_a_time(db, aula, ws, monkeypatch):
    monkeypatch.setattr(activity, "current_week", lambda now=None: WEEK)
    monkeypatch.setattr(activity_routes.singletons.runner, "handlers", {activity_routes.DIGEST_KIND: None})
    _conversation(
        ws,
        aula.sara.id,
        "20261006T100000Z-222222",
        [(at(6, 9, n), f"duda {n}", "theory", "Variable", None, None) for n in range(10)],
    )
    live = SimpleNamespace(kind=activity_routes.DIGEST_KIND, params={"week": WEEK})
    monkeypatch.setattr(activity_routes.singletons.runner, "running", lambda slug=None: [live])

    with pytest.raises(HTTPException) as refused:
        activity_routes.write_digest(WEEK, access=aula.teacher, db=db)

    assert refused.value.status_code == 409
    assert refused.value.headers == {"X-Error-Code": activity_routes.DIGEST_BUSY}


def test_the_digest_is_its_author_s_and_background_work():
    from server.app import create_app
    from server.jobs.catalogue import BACKGROUND, JOB_CLASS, PRIVATE_KINDS

    create_app()

    assert digest_job.DIGEST in PRIVATE_KINDS
    assert JOB_CLASS[digest_job.DIGEST] == BACKGROUND
    assert activity.TUTOR_READER is tutor_activity.read


def test_a_course_progress_bounds_which_units_count_as_unpractised(ws):
    curriculum.save(ws, ["Variable"], _graph(ws))

    progress = curriculum.load(ws, _graph(ws))["concepts"]
    block = activity.week(activity.read_scope(ws, CLASS), WEEK, _graph(ws), progress=progress, now=NOW)

    assert [(u["unit"], u["covered"]) for u in block["exercises"]["by_unit"]] == [
        ("Fundamentos", True),
        ("Avanzado", False),
    ]
