from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.db import Base, repository
from server.db import generations as db_generations
from server.jobs import handlers
from server.jobs.models import Job
from variant_generator.core import progress


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
def factory(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scope():
        session = maker()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise

    monkeypatch.setattr(handlers, "session_scope", scope)
    with maker() as session:
        repository.ensure_workspace(session, "aula")
        session.commit()
    return maker


@pytest.fixture
def stubbed(monkeypatch):
    context = SimpleNamespace(
        workspace=None,
        knowledge_graph=None,
        exemplars_profile=SimpleNamespace(item_type=lambda _key: _Type()),
    )
    monkeypatch.setattr(handlers.deps, "require_inference", lambda: None)
    monkeypatch.setattr(handlers, "context_for", lambda job: context)
    monkeypatch.setattr(handlers.curriculum_store, "resolve", lambda ws, kg, given: given or [])


def _save(factory, text: str, concepts: list[str], item_type: str = "ejercicio") -> None:
    with factory() as session:
        workspace = repository.ensure_workspace(session, "aula")
        db_generations.save_generation(
            session,
            workspace_id=workspace.id,
            user_id=None,
            job_id=None,
            item_type=item_type,
            item={"enunciado": text},
            concepts=concepts,
            curriculum=[],
            fixed={},
            instructions=None,
            think=True,
            thinking=None,
        )
        session.commit()


def _run(job: Job, monkeypatch) -> dict:
    seen: dict = {}

    def fake_generate(context, **kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(handlers.stages, "generate", fake_generate)
    with progress.emitting(_Emitter()):
        handlers.handle_generate(job, None)
    return seen


def test_recent_items_filters_by_modality_and_concept_overlap(factory):
    _save(factory, "sobre bucles", ["Bucles"])
    _save(factory, "sobre listas", ["Listas"])
    _save(factory, "otra modalidad", ["Bucles"], item_type="analisis")
    _save(factory, "bucles y listas", ["Bucles", "Listas"])

    with factory() as session:
        workspace = repository.ensure_workspace(session, "aula")
        items = db_generations.recent_items(
            session, workspace.id, item_type="ejercicio", concepts=["Bucles"], limit=10
        )
    assert [i["enunciado"] for i in items] == ["bucles y listas", "sobre bucles"]


def test_recent_items_without_targets_takes_the_newest_of_the_modality(factory):
    for text in ("uno", "dos", "tres"):
        _save(factory, text, ["Bucles"])

    with factory() as session:
        workspace = repository.ensure_workspace(session, "aula")
        items = db_generations.recent_items(
            session, workspace.id, item_type="ejercicio", concepts=None, limit=2
        )
    assert [i["enunciado"] for i in items] == ["tres", "dos"]


def test_the_saved_scenarios_reach_the_generator(factory, stubbed, monkeypatch):
    _save(factory, "el enunciado guardado", ["Bucles"])
    job = Job(kind="generate", params={"n": 1, "concepts": ["Bucles"]}, workspace="aula")
    seen = _run(job, monkeypatch)
    assert seen["avoid"] == ["el enunciado guardado"]


def test_zero_disables_the_reminder(factory, stubbed, monkeypatch):
    _save(factory, "el enunciado guardado", ["Bucles"])
    monkeypatch.setattr(handlers.config, "GENERATION_AVOID_RECENT", 0)
    job = Job(kind="generate", params={"n": 1, "concepts": ["Bucles"]}, workspace="aula")
    seen = _run(job, monkeypatch)
    assert seen["avoid"] == []


def test_a_database_failure_generates_without_the_reminder(factory, stubbed, monkeypatch):
    @contextmanager
    def broken():
        raise RuntimeError("sin base de datos")
        yield

    monkeypatch.setattr(handlers, "session_scope", broken)
    job = Job(kind="generate", params={"n": 1, "concepts": ["Bucles"]}, workspace="aula")
    seen = _run(job, monkeypatch)
    assert seen["avoid"] == []
