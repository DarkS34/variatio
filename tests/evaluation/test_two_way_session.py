"""A session is the system against ONE rival drawn by its seed, on two cards.

What is pinned: the draw (both rivals, both orders, reproducible from the seed), that only
the two drawn arms are generated, that the screen is handed exactly two cards and refuses a
third position, and that a session recorded with three cards before 2026-09-08 still reads,
copies and exports as three — the shape is the session's own `shuffle`, never a constant.
"""

import csv
import io

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from evaluation import FAILED, RIVALS, SYSTEM, ArmResult, EvaluationSession, draw_session
from evaluation import run as evaluation_run
from evaluation.api import jobs as evaluation_jobs
from evaluation.api import queries
from evaluation.api import router as evaluation_router
from evaluation.api import store as evaluation_store
from server.db.models import Base, User, Workspace
from server.jobs.catalogue import Job
from variatio import config, settings


# THE DRAW --------------------------------------------------------------------------------


def test_a_session_is_the_system_and_one_rival():
    for seed in range(50):
        order, think = draw_session(seed)
        assert len(order) == 2
        assert SYSTEM in order
        assert [arm for arm in order if arm != SYSTEM][0] in RIVALS
        assert isinstance(think, bool)


def test_both_rivals_and_both_orders_occur():
    draws = {tuple(draw_session(seed)[0]) for seed in range(200)}
    assert draws == {
        ("system", "naive"),
        ("naive", "system"),
        ("system", "rag"),
        ("rag", "system"),
    }


def test_the_draw_is_reproducible_from_the_seed_alone():
    assert draw_session(42) == draw_session(42)


# WHAT IS GENERATED -----------------------------------------------------------------------


@pytest.fixture
def offered(monkeypatch):
    monkeypatch.setattr(config, "GENERATION_MODELS", ["el-rapido"])
    monkeypatch.setattr(config, "VARIANT_GENERATION_LLM", "el-rapido")
    monkeypatch.setattr(config, "FIXED_EFFORT_MODELS", [])
    monkeypatch.setattr(config, "FIXED_EFFORT_LEVELS", {})
    real = settings.values

    def patched():
        out = real()
        out["evaluation.local_model"] = None
        return out

    monkeypatch.setattr(settings, "values", patched)


class _Type:
    key = "ejercicio"
    label = "Ejercicio"
    field_specs: dict = {}


class _Profile:
    def item_type(self, key):
        return _Type()


class _Context:
    exemplars_profile = _Profile()
    language = "es"


def _run_capturing(monkeypatch) -> list[str]:
    """Stub everything after the commission is built and keep which arms were run."""
    seen: list[str] = []

    def fake_arm(arm, commission, context):
        seen.append(arm)
        return ArmResult(arm, FAILED, None, "", "", "", "", [], 0)

    monkeypatch.setattr(evaluation_run, "_validate", lambda *a: None)
    monkeypatch.setattr(evaluation_run, "_screen", lambda *a: None)
    monkeypatch.setattr(evaluation_run, "_tag", lambda *a: None)
    monkeypatch.setattr(evaluation_run, "_safe_run", fake_arm)
    return seen


def test_only_the_two_drawn_arms_are_run(offered, monkeypatch):
    seen = _run_capturing(monkeypatch)
    session = evaluation_run.evaluate(_Context(), concepts=["Función"], seed=7)
    order, think = draw_session(7)
    assert sorted(seen) == sorted(order)
    assert session.shuffle == order
    assert set(session.arms) == set(order)
    assert session.cards == 2
    assert session.rival in RIVALS
    assert session.think is think


def test_the_commercial_arm_is_not_called_when_rag_is_the_rival(offered, monkeypatch):
    seed = next(s for s in range(100) if "rag" in draw_session(s)[0])
    seen = _run_capturing(monkeypatch)
    evaluation_run.evaluate(_Context(), concepts=["Función"], seed=seed)
    assert "naive" not in seen


def test_the_job_warms_the_rag_index_only_when_the_draw_needs_it(monkeypatch):
    """The seed is settled in the job so it can ask what the session will need."""
    warmed: list[object] = []
    ran: list[int] = []

    class _Control:
        def emit(self, kind, payload):
            pass

        def should_cancel(self):
            return False

    class _Db:
        pass

    class _Scope:
        def __enter__(self):
            return _Db()

        def __exit__(self, *a):
            return False

    def fake_evaluate(context, **kwargs):
        ran.append(kwargs["seed"])
        order, think = draw_session(kwargs["seed"])
        return EvaluationSession(
            id="s",
            created_at=0.0,
            concepts=[],
            item_type="ejercicio",
            fixed={},
            curriculum=[],
            instructions="",
            seed=kwargs["seed"],
            shuffle=order,
            arms={
                arm: ArmResult(arm, FAILED, None, "", "", "", "", [], 0) for arm in order
            },
            think=think,
        )

    class _Ws:
        id = 1

    monkeypatch.setattr(evaluation_jobs.deps, "require_inference", lambda: None)
    monkeypatch.setattr(evaluation_jobs, "context_for", lambda job: _Context())
    monkeypatch.setattr(evaluation_jobs.rag_arm, "warm", lambda ws: warmed.append(ws))
    monkeypatch.setattr(evaluation_jobs.evaluation_run, "evaluate", fake_evaluate)
    monkeypatch.setattr(evaluation_jobs, "session_scope", lambda: _Scope())
    monkeypatch.setattr(evaluation_jobs.repository, "get_workspace", lambda db, slug: _Ws())
    monkeypatch.setattr(evaluation_jobs.evaluation_store, "save", lambda *a: None)
    _Context.workspace = object()

    with_rag = next(s for s in range(100) if "rag" in draw_session(s)[0])
    without = next(s for s in range(100) if "rag" not in draw_session(s)[0])

    result = evaluation_jobs.handle_evaluate(
        Job(kind="evaluate", params={"seed": with_rag}, workspace="lab", user_id=1), _Control()
    )
    assert warmed and ran == [with_rag]
    assert result == {"session_id": "s", "arms": 2, "produced": 0}

    warmed.clear()
    evaluation_jobs.handle_evaluate(
        Job(kind="evaluate", params={"seed": without}, workspace="lab", user_id=1), _Control()
    )
    assert warmed == []


# WHAT THE SCREEN IS HANDED ---------------------------------------------------------------


def _arm(name):
    return {
        "arm": name,
        "status": "ok",
        "item": {"enunciado": f"el de {name}"},
        "raw_response": "{}",
        "prompt": "",
        "model": "modelo",
        "provider": "local",
        "exemplar_ids": [],
        "elapsed_ms": 1200,
        "error": None,
        "checks": None,
        "retried": 0,
    }


def _trace(session_id, shuffle):
    return {
        "id": session_id,
        "created_at": 1787000000.0,
        "job_id": "job1",
        "set_id": session_id,
        "assigned_by": None,
        "concepts": ["Recursividad"],
        "item_type": "escritura_codigo",
        "fixed": {},
        "curriculum": [],
        "instructions": "",
        "seed": 42,
        "shuffle": shuffle,
        "think": False,
        "arms": {name: _arm(name) for name in shuffle},
        "triage": {},
        "choice": None,
        "choice_arm": None,
        "chosen_at": None,
        "opened_at": None,
        "declined_at": None,
        "evaluator_note": None,
        "rating": None,
    }


TWO = _trace("dos000000001", ["naive", "system"])
THREE = _trace("tres00000001", ["naive", "rag", "system"])


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    workspace = Workspace(slug="asignatura", name="Asignatura")
    session.add(workspace)
    session.flush()
    session.add(User(id=1, username="ana", name="ana", password_hash="x"))
    session.flush()
    for trace in (TWO, THREE):
        queries.upsert_evaluation(session, trace["id"], workspace.id, 1, trace)
    yield session
    session.close()


def test_a_two_card_session_is_rendered_as_two_positions():
    payload = evaluation_router._payload(EvaluationSession.from_dict(TWO))
    assert [p["position"] for p in payload["positions"]] == [1, 2]
    # Blind: neither the arm nor the rival travels.
    assert all("arm" not in p for p in payload["positions"])


def test_a_session_recorded_with_three_cards_is_still_rendered_as_three():
    payload = evaluation_router._payload(EvaluationSession.from_dict(THREE))
    assert [p["position"] for p in payload["positions"]] == [1, 2, 3]


def test_a_third_position_is_refused_on_a_two_card_session(db):
    row = queries.get_evaluation(db, TWO["id"])
    with pytest.raises(ValueError, match="between 1 and 2"):
        evaluation_store.record_triage(db, row, 3, "yes")
    with pytest.raises(ValueError, match="between 1 and 2"):
        evaluation_store.record_choice(db, row, 3)


def test_the_second_position_is_a_valid_choice_and_names_its_arm(db):
    row = queries.get_evaluation(db, TWO["id"])
    evaluation_store.record_triage(db, row, 2, "yes")
    db.refresh(row)
    session = evaluation_store.record_choice(db, row, 2)
    assert session.choice_arm == "system"
    assert session.triage_by_arm() == {"system": "yes"}


def test_a_third_position_is_still_accepted_on_a_three_card_session(db):
    row = queries.get_evaluation(db, THREE["id"])
    session = evaluation_store.record_choice(db, row, 3)
    assert session.choice_arm == "system"


# WHAT THE CSV SAYS -----------------------------------------------------------------------


def test_the_export_names_the_rival_and_leaves_the_third_position_blank(db):
    rows = {
        line["session_id"]: line
        for line in csv.DictReader(io.StringIO(evaluation_store.export_csv(evaluation_store.headers(db))))
    }
    assert rows[TWO["id"]]["rival"] == "naive"
    assert rows[TWO["id"]]["position_3"] == ""
    assert rows[THREE["id"]]["rival"] == ""
    assert rows[THREE["id"]]["position_3"] == "system"
