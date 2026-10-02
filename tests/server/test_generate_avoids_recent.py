"""The statements of this account's last saved exercises reach the prompt, to be avoided.

Its own and nobody else's: what this feeds is somebody's prompt, so a colleague's statement
here would be read by another door than the one the listing closes.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from server import generations as store
from server.jobs import handlers
from server.jobs.catalogue import Job
from variatio.core import paths, progress

START = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


class _Type:
    key = "ejercicio"
    label = "Ejercicio"

    @staticmethod
    def primary_text(item: dict) -> str:
        if "enunciado" not in item:
            raise ValueError("missing primary field")
        return str(item["enunciado"] or "")


class _Emitter:
    def emit(self, kind: str, payload: dict) -> None:
        pass

    def should_cancel(self) -> bool:
        return False


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    return paths.workspace("aula")


@pytest.fixture
def stubbed(monkeypatch, ws):
    context = SimpleNamespace(
        workspace=None,
        knowledge_graph=None,
        exemplars_profile=SimpleNamespace(item_type=lambda _key: _Type()),
    )
    monkeypatch.setattr(handlers.deps, "require_inference", lambda: None)
    monkeypatch.setattr(handlers, "context_for", lambda job: context)
    monkeypatch.setattr(handlers.curriculum_store, "resolve", lambda ws, kg, given: given or [])


_written = iter(range(10_000))


def _save(ws, text: str, concepts: list[str], item_type: str = "ejercicio", user_id: int = 7):
    """Save one exercise a minute after the previous one, so their order is unambiguous."""
    minute = next(_written)
    store.save(
        ws,
        user_id,
        "job",
        minute,
        {
            "commission": {"concepts": concepts},
            "resolved": {"targets": concepts, "item_type": item_type},
            "output": {"item": {"enunciado": text}},
        },
        now=START + timedelta(minutes=minute),
    )


def _run(job: Job, monkeypatch) -> dict:
    seen: dict = {}

    def fake_generate(context, **kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(handlers.entrypoints, "generate", fake_generate)
    with progress.emitting(_Emitter()):
        handlers.handle_generate(job, None)
    return seen


def _job(user_id: int | None = 7) -> Job:
    return Job(kind="generate", params={"n": 1, "concepts": ["Bucles"]}, workspace="aula", user_id=user_id)


def test_recent_items_filters_by_modality_and_concept_overlap(ws):
    _save(ws, "sobre bucles", ["Bucles"])
    _save(ws, "sobre listas", ["Listas"])
    _save(ws, "otra modalidad", ["Bucles"], item_type="analisis")
    _save(ws, "bucles y listas", ["Bucles", "Listas"])

    items = store.recent_items(ws, 7, item_type="ejercicio", concepts=["Bucles"], limit=10)
    assert [i["enunciado"] for i in items] == ["bucles y listas", "sobre bucles"]


def test_recent_items_without_targets_takes_the_newest_of_the_modality(ws):
    for text in ("uno", "dos", "tres"):
        _save(ws, text, ["Bucles"])

    items = store.recent_items(ws, 7, item_type="ejercicio", concepts=None, limit=2)
    assert [i["enunciado"] for i in items] == ["tres", "dos"]


def test_the_saved_scenarios_reach_the_generator(ws, stubbed, monkeypatch):
    _save(ws, "el enunciado guardado", ["Bucles"])
    seen = _run(_job(), monkeypatch)
    assert seen["avoid"] == ["el enunciado guardado"]


def test_another_accounts_statements_never_reach_the_prompt(ws, stubbed, monkeypatch):
    _save(ws, "el de otra cuenta", ["Bucles"], user_id=8)
    seen = _run(_job(), monkeypatch)
    assert seen["avoid"] == []


def test_a_job_with_no_author_reads_nothing(ws, stubbed, monkeypatch):
    _save(ws, "sin dueño", ["Bucles"], user_id=None)
    _save(ws, "de alguien", ["Bucles"])
    seen = _run(_job(user_id=None), monkeypatch)
    assert seen["avoid"] == []


def test_zero_disables_the_reminder(ws, stubbed, monkeypatch):
    _save(ws, "el enunciado guardado", ["Bucles"])
    monkeypatch.setattr(handlers.config, "GENERATION_AVOID_RECENT", 0)
    seen = _run(_job(), monkeypatch)
    assert seen["avoid"] == []


def test_an_unreadable_store_generates_without_the_reminder(ws, stubbed, monkeypatch):
    def broken(*args, **kwargs):
        raise PermissionError("sin permiso de lectura")

    monkeypatch.setattr(handlers.generations_store, "recent_items", broken)
    seen = _run(_job(), monkeypatch)
    assert seen["avoid"] == []
