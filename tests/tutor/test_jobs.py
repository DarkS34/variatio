"""The two jobs: a turn writes its reply into the author's file, a build writes the draft."""

import json
from types import SimpleNamespace

import pytest

from server.jobs.catalogue import Job
from tutor import paths
from tutor.api import jobs, store
from tutor.turn import TurnResult
from variatio.core import progress

from .conftest import SOURCES

ANA = 1


@pytest.fixture
def wired(tutor_context, monkeypatch):
    ws = tutor_context.workspace
    monkeypatch.setattr(jobs.installation, "workspace_for", lambda slug: ws)
    monkeypatch.setattr(jobs.deps, "require_inference", lambda: None)
    monkeypatch.setattr(jobs, "context_for", lambda job: tutor_context)
    monkeypatch.setattr(jobs.entrypoints, "load_concept_sources", lambda ws: SOURCES)
    monkeypatch.setattr(jobs, "index_for", lambda ws, sources, chars: None)
    return ws


def pending_turn(ws, message="¿Qué es la recursividad?"):
    record = store.create(ws, ANA, message)
    job = Job(kind=jobs.TURN, params={"conversation": record["id"], "turn": 0}, workspace="ws", user_id=ANA)
    record["pending"] = {"job_id": job.id, "turn": 0}
    store.write(ws, ANA, record)
    return record, job


def test_a_turn_appends_the_reply_moves_the_state_and_frees_the_conversation(wired, monkeypatch):
    record, job = pending_turn(wired)
    seen = {}

    def answer(context, **kwargs):
        seen.update(kwargs)
        return TurnResult(text="¿Qué sabes de funciones?", kind="theory", decided_by="model",
                          state={"focus": ["Recursividad"], "trail": ["Recursividad"]},
                          prompt="el prompt")

    monkeypatch.setattr(jobs, "run_turn", answer)

    result = jobs.handle_turn(job, SimpleNamespace())

    saved = store.get(wired, ANA, record["id"])
    assert result == {"conversation": record["id"], "turn": 1}
    assert saved["pending"] is None
    assert saved["turns"][1]["text"] == "¿Qué sabes de funciones?" and saved["turns"][1]["kind"] == "theory"
    assert saved["state"]["focus"] == ["Recursividad"]
    assert seen["message"] == "¿Qué es la recursividad?" and seen["history"] == []
    assert "¿Qué" not in json.dumps(result), "the job's result is public: it carries no text"


def test_a_turn_that_fails_marks_the_message_and_frees_the_conversation(wired, monkeypatch):
    record, job = pending_turn(wired)

    def broken(context, **kwargs):
        raise RuntimeError("el motor no contesta")

    monkeypatch.setattr(jobs, "run_turn", broken)

    with pytest.raises(RuntimeError):
        jobs.handle_turn(job, SimpleNamespace())
    saved = store.get(wired, ANA, record["id"])
    assert saved["pending"] is None and saved["turns"][0]["failed"] == "failed"


def test_a_cancelled_turn_is_marked_as_such(wired, monkeypatch):
    record, job = pending_turn(wired)

    def cancelled(context, **kwargs):
        raise progress.Cancelled("cancelled by the user")

    monkeypatch.setattr(jobs, "run_turn", cancelled)

    with pytest.raises(progress.Cancelled):
        jobs.handle_turn(job, SimpleNamespace())
    assert store.get(wired, ANA, record["id"])["turns"][0]["failed"] == "cancelled"


def test_a_job_naming_a_turn_the_conversation_does_not_wait_for_is_refused(wired):
    record, job = pending_turn(wired)
    stranger = Job(kind=jobs.TURN, params={"conversation": record["id"], "turn": 0}, workspace="ws", user_id=ANA)

    with pytest.raises(ValueError):
        jobs.handle_turn(stranger, SimpleNamespace())


def test_a_build_writes_the_draft_and_retires_the_teacher_s_copy_to_the_history(wired, monkeypatch):
    wired.artifacts_dir.mkdir(parents=True, exist_ok=True)
    paths.criteria_path(wired).write_text(json.dumps({"general": [{"text": "Del docente."}]}), encoding="utf-8")
    monkeypatch.setattr(jobs, "cut_corpus", lambda ws, sources, chars: [])
    monkeypatch.setattr(
        jobs,
        "build_criteria",
        lambda context, sources, passages: {
            "general": [{"text": "Del borrador.", "strength": "must"}],
            "units": {"Avanzado": [{"text": "Caso base.", "concepts": ["Recursividad"]}]},
            "forbidden_terms": [],
            "built": {"model": "m"},
        },
    )

    result = jobs.handle_criteria(Job(kind=jobs.CRITERIA, workspace="ws", user_id=ANA), SimpleNamespace())

    assert result == {"general": 1, "units": 1, "forbidden_terms": 0}
    draft = json.loads(paths.criteria_draft_path(wired).read_text(encoding="utf-8"))
    assert draft["general"][0]["text"] == "Del borrador." and draft["built"] == {"model": "m"}
    assert not paths.criteria_path(wired).exists()
    assert list((wired.history_dir / paths.CRITERIA_STEM).iterdir())


def test_only_the_turn_s_steps_reach_the_workspace_s_stream(wired, monkeypatch):
    record, job = pending_turn(wired)
    heard = []
    control = SimpleNamespace(emit=lambda kind, payload: heard.append(kind), should_cancel=lambda: False)

    def answer(context, **kwargs):
        progress.emit("guardrail", ok=False, criteria="jailbreak", checked=True)
        with progress.step("tutor.reply.1", "Writing the reply"):
            pass
        return TurnResult(text="¿Y bien?", kind="theory", decided_by="model", state={})

    monkeypatch.setattr(jobs, "run_turn", answer)
    token = progress.set_emitter(control)
    try:
        jobs.handle_turn(job, control)
    finally:
        progress.reset_emitter(token)

    assert "guardrail" not in heard
    assert heard == ["step.started", "step.finished"]


def test_the_first_reply_that_works_on_the_subject_titles_the_conversation_once(wired, monkeypatch):
    record, job = pending_turn(wired, message="Hola, necesito ayuda con esto de llamarse a sí misma")
    asked = []

    def name(messages, concepts, **kwargs):
        asked.append((messages, concepts))
        return "Recursividad"

    def answer(context, **kwargs):
        return TurnResult(text="¿Qué sabes?", kind="theory", decided_by="model",
                          state={"focus": ["Recursividad"], "trail": ["Recursividad"]})

    monkeypatch.setattr(jobs, "name_conversation", name)
    monkeypatch.setattr(jobs, "run_turn", answer)

    jobs.handle_turn(job, SimpleNamespace())

    saved = store.get(wired, ANA, record["id"])
    assert saved["title"] == "Recursividad" and saved["titled"] is True
    assert asked == [(["Hola, necesito ayuda con esto de llamarse a sí misma"], ["Recursividad"])]


def test_a_greeting_leaves_the_first_line_as_the_title(wired, monkeypatch):
    record, job = pending_turn(wired, message="Hola")
    monkeypatch.setattr(jobs, "name_conversation", lambda *a, **k: pytest.fail("no title for a greeting"))
    monkeypatch.setattr(
        jobs, "run_turn",
        lambda context, **kwargs: TurnResult(text="¡Hola! ¿Qué trabajamos?", kind="social", decided_by="model", state={}),
    )

    jobs.handle_turn(job, SimpleNamespace())

    saved = store.get(wired, ANA, record["id"])
    assert saved["title"] == "Hola" and saved["titled"] is False


def test_a_title_is_cleaned_or_refused():
    from tutor.title import clean

    assert clean(' «recursividad y caso base». ') == "Recursividad y caso base"
    assert clean("") is None and clean("x" * 61) is None and clean('{"title": 1}') is None


def test_the_concept_chosen_for_a_message_reaches_its_turn(wired, monkeypatch):
    record = store.create(wired, ANA, "Explícamelo", concept="Recursividad")
    job = Job(kind=jobs.TURN, params={"conversation": record["id"], "turn": 0}, workspace="ws", user_id=ANA)
    record["pending"] = {"job_id": job.id, "turn": 0}
    store.write(wired, ANA, record)
    seen = {}

    def answer(context, **kwargs):
        seen.update(kwargs)
        return TurnResult(text="¿Qué sabes?", kind="social", decided_by="model", state={})

    monkeypatch.setattr(jobs, "run_turn", answer)

    jobs.handle_turn(job, SimpleNamespace())

    assert seen["chosen"] == "Recursividad"
