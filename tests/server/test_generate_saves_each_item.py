from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.db import Base, Generation, repository
from server.jobs import handlers
from server.jobs.catalogue import Job
from variatio.core import progress
from variatio.core.progress import Cancelled


class _Item:
    def __init__(self, text: str):
        self.text = text

    def model_dump(self, mode: str = "json") -> dict:
        return {"enunciado": self.text}


def _variant(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        item=_Item(text), item_type="ejercicio", thinking=None, checks=None, retried=0
    )


class _Emitter:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def emit(self, kind: str, payload: dict) -> None:
        self.events.append((kind, payload))

    def should_cancel(self) -> bool:
        return False


@pytest.fixture
def make(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scope():
        session = factory()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise

    monkeypatch.setattr(handlers, "session_scope", scope)
    with factory() as session:
        repository.ensure_workspace(session, "aula")
        session.commit()
    return factory


@pytest.fixture
def stubbed(monkeypatch):
    item_type = SimpleNamespace(key="ejercicio", label="Ejercicio")
    context = SimpleNamespace(
        workspace=None,
        knowledge_graph=None,
        exemplars_profile=SimpleNamespace(item_type=lambda _key: item_type),
    )
    monkeypatch.setattr(handlers.deps, "require_inference", lambda: None)
    monkeypatch.setattr(handlers, "context_for", lambda job: context)
    monkeypatch.setattr(handlers.curriculum_store, "resolve", lambda ws, kg, given: given or [])


def _run(job: Job) -> tuple[dict | None, _Emitter, BaseException | None]:
    emitter = _Emitter()
    with progress.emitting(emitter):
        try:
            return handlers.handle_generate(job, None), emitter, None
        except BaseException as exc:  # noqa: BLE001
            return None, emitter, exc


def _rows(factory) -> list[Generation]:
    with factory() as session:
        return list(session.scalars(select(Generation).order_by(Generation.id)))


def test_each_validated_item_is_saved_as_it_arrives(make, stubbed, monkeypatch):
    def fake_generate(context, **kwargs):
        accepted = [_variant("uno"), _variant("dos")]
        for i, result in enumerate(accepted):
            kwargs["on_accepted"](result, i + 1)
        return accepted

    monkeypatch.setattr(handlers.entrypoints, "generate", fake_generate)
    job = Job(kind="generate", params={"n": 2, "concepts": ["Bucles"]}, workspace="aula")
    result, emitter, _ = _run(job)

    rows = _rows(make)
    assert [r.item["enunciado"] for r in rows] == ["uno", "dos"]
    assert all(r.concepts == ["Bucles"] for r in rows)
    assert result["saved"] == 2
    assert [i["saved_id"] for i in result["items"]] == [rows[0].id, rows[1].id]
    saved = [p for k, p in emitter.events if k == "item.saved"]
    assert saved == [{"index": 1, "id": rows[0].id}, {"index": 2, "id": rows[1].id}]


# A statement without its parameters can be read but neither judged nor reproduced, and the
# model is one of them: two offered models differ by minutes and by how much they
# deliberate, so a row that does not name one cannot be read beside the next.
def test_the_row_records_the_model_the_commission_chose(make, stubbed, monkeypatch):
    monkeypatch.setattr(handlers.config, "GENERATION_MODELS", ["el-rapido", "el-lento"])

    def fake_generate(context, **kwargs):
        kwargs["on_accepted"](_variant("uno"), 1)
        return [_variant("uno")]

    monkeypatch.setattr(handlers.entrypoints, "generate", fake_generate)
    job = Job(
        kind="generate",
        params={"n": 1, "concepts": ["Bucles"], "model": "el-lento"},
        workspace="aula",
    )
    result, _, error = _run(job)

    assert error is None
    assert result["model"] == "el-lento"
    assert [r.model for r in _rows(make)] == ["el-lento"]


def test_a_commission_naming_no_model_records_the_default_one(make, stubbed, monkeypatch):
    monkeypatch.setattr(handlers.config, "GENERATION_MODELS", ["el-rapido", "el-lento"])

    def fake_generate(context, **kwargs):
        kwargs["on_accepted"](_variant("uno"), 1)
        return [_variant("uno")]

    monkeypatch.setattr(handlers.entrypoints, "generate", fake_generate)
    job = Job(kind="generate", params={"n": 1, "concepts": ["Bucles"]}, workspace="aula")
    result, _, _ = _run(job)

    assert result["model"] == "el-rapido"
    assert [r.model for r in _rows(make)] == ["el-rapido"]


# The submit route refused it already, so getting here means the offered list changed
# under a job that was waiting: the job fails saying so instead of quietly running on
# whatever the installation offers today.
def test_a_model_that_stopped_being_offered_stops_the_job(make, stubbed, monkeypatch):
    monkeypatch.setattr(handlers.config, "GENERATION_MODELS", ["el-que-hay"])
    monkeypatch.setattr(handlers.entrypoints, "generate", lambda *a, **k: pytest.fail("no llega"))
    job = Job(
        kind="generate",
        params={"n": 1, "concepts": ["Bucles"], "model": "el-que-ya-no"},
        workspace="aula",
    )
    result, _, error = _run(job)

    assert result is None
    assert isinstance(error, handlers.entrypoints.UnofferedModelError)
    assert _rows(make) == []


def test_a_cancelled_run_keeps_what_it_validated(make, stubbed, monkeypatch):
    def fake_generate(context, **kwargs):
        kwargs["on_accepted"](_variant("uno"), 1)
        kwargs["on_accepted"](_variant("dos"), 2)
        raise Cancelled("cancelled by the user")

    monkeypatch.setattr(handlers.entrypoints, "generate", fake_generate)
    job = Job(kind="generate", params={"n": 5, "concepts": ["Bucles"]}, workspace="aula")
    result, _, error = _run(job)

    assert result is None and isinstance(error, Cancelled)
    assert [r.item["enunciado"] for r in _rows(make)] == ["uno", "dos"]


def test_a_database_failure_loses_the_record_and_nothing_else(make, stubbed, monkeypatch):
    @contextmanager
    def broken():
        raise RuntimeError("sin base de datos")
        yield

    monkeypatch.setattr(handlers, "session_scope", broken)

    def fake_generate(context, **kwargs):
        kwargs["on_accepted"](_variant("uno"), 1)
        return [_variant("uno")]

    monkeypatch.setattr(handlers.entrypoints, "generate", fake_generate)
    job = Job(kind="generate", params={"n": 1, "concepts": ["Bucles"]}, workspace="aula")
    result, emitter, error = _run(job)

    assert error is None
    assert result["produced"] == 1 and result["saved"] == 0
    assert result["items"][0]["saved_id"] is None
    assert not [k for k, _ in emitter.events if k == "item.saved"]



# `or 1` was wrong on a falsy zero: a commission of "generate 0 items" produced one and then
# reported `requested: 1`, so the row kept a commission nobody made. An absent `n` still
# means one; a zero has to reach the generator, which is what refuses it.
def test_a_count_of_zero_is_not_silently_turned_into_one(make, stubbed, monkeypatch):
    seen = {}

    def fake_generate(context, **kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(handlers.entrypoints, "generate", fake_generate)
    job = Job(kind="generate", params={"n": 0, "concepts": ["Bucles"]}, workspace="aula")
    result, _, error = _run(job)

    assert error is None
    assert seen["n"] == 0
    assert result["requested"] == 0
    assert not _rows(make)


def test_an_absent_count_still_means_one(make, stubbed, monkeypatch):
    seen = {}

    def fake_generate(context, **kwargs):
        seen.update(kwargs)
        kwargs["on_accepted"](_variant("uno"), 1)
        return [_variant("uno")]

    monkeypatch.setattr(handlers.entrypoints, "generate", fake_generate)
    job = Job(kind="generate", params={"concepts": ["Bucles"]}, workspace="aula")
    result, _, error = _run(job)

    assert error is None
    assert seen["n"] == 1
    assert result["requested"] == 1
