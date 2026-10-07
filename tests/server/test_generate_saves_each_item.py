"""Every validated item is a file the moment it validates, with how it was made.

`commission` is what was asked and `resolved` what ran: two models differ by minutes and by
how much they deliberate, and an installation may lock a model's effort, so a record that
keeps only one of the two cannot be read beside the next.
"""

import json
from types import SimpleNamespace

import pytest

from server import generations as store
from server.jobs import handlers
from server.jobs.catalogue import Job
from variatio.core import paths, progress
from variatio.core.progress import Cancelled


class _Item:
    def __init__(self, text: str):
        self.text = text

    def model_dump(self, mode: str = "json") -> dict:
        return {"enunciado": self.text}


def _variant(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        item=_Item(text),
        item_type="ejercicio",
        thinking=None,
        checks=None,
        retried=0,
        prompt=f"prompt de {text}",
        provenance={"targets": ["Bucles"], "forbidden": ["Recursividad"], "few_shot": []},
    )


class _Emitter:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def emit(self, kind: str, payload: dict) -> None:
        self.events.append((kind, payload))

    def should_cancel(self) -> bool:
        return False


@pytest.fixture
def stubbed(monkeypatch, tmp_path):
    # Per test, so one test's files are never another's: the session-wide redirect is
    # shared by every test that names the same slug.
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    item_type = SimpleNamespace(key="ejercicio", label="Ejercicio")
    context = SimpleNamespace(
        workspace=None,
        knowledge_graph=None,
        exemplars_profile=SimpleNamespace(item_type=lambda _key: item_type),
    )
    monkeypatch.setattr(handlers.deps, "require_inference", lambda: None)
    monkeypatch.setattr(handlers, "context_for", lambda job: context)
    monkeypatch.setattr(
        handlers.curriculum_store, "resolve", lambda ws, kg, given: given or []
    )


def _run(job: Job) -> tuple[dict | None, _Emitter, BaseException | None]:
    emitter = _Emitter()
    with progress.emitting(emitter):
        try:
            return handlers.handle_generate(job, None), emitter, None
        except BaseException as exc:  # noqa: BLE001
            return None, emitter, exc


def _records(user_id: int | None = 7) -> list[dict]:
    """Every file of one account, in the order it was written."""
    ws = paths.workspace("aula")
    records, _ = store.list_for(ws, user_id, limit=1000)
    return list(reversed(records))


def _accepting(*texts: str):
    def fake_generate(context, **kwargs):
        accepted = [_variant(text) for text in texts]
        for i, result in enumerate(accepted):
            kwargs["on_accepted"](result, i + 1)
        return accepted

    return fake_generate


def _job(**params) -> Job:
    return Job(
        kind="generate",
        params={"n": 1, "concepts": ["Bucles"], **params},
        workspace="aula",
        user_id=7,
        user_name="Ana",
    )


def test_each_validated_item_is_saved_as_it_arrives(stubbed, monkeypatch):
    monkeypatch.setattr(handlers.entrypoints, "generate", _accepting("uno", "dos"))
    result, emitter, _ = _run(_job(n=2))

    records = _records()
    assert [store.item_of(r)["enunciado"] for r in records] == ["uno", "dos"]
    assert all(r["commission"]["concepts"] == ["Bucles"] for r in records)
    assert result["saved"] == 2
    ids = [r["id"] for r in records]
    assert all(isinstance(i, str) for i in ids)
    assert [i["saved_id"] for i in result["items"]] == ids
    saved = [p for k, p in emitter.events if k == "item.saved"]
    assert saved == [{"index": 1, "id": ids[0]}, {"index": 2, "id": ids[1]}]


def test_the_file_is_under_the_author_and_names_the_run(stubbed, monkeypatch):
    monkeypatch.setattr(handlers.entrypoints, "generate", _accepting("uno", "dos"))
    job = _job(n=2)
    _run(job)

    [first, second] = _records()
    path = paths.workspace("aula").generations_dir / "user_7" / f"{second['id']}.json"
    assert json.loads(path.read_text(encoding="utf-8"))["id"] == second["id"]
    assert second["author"] == {"id": 7, "username": None, "name": "Ana"}
    assert second["job"] == {"id": job.id, "requested": 2, "index": 2}
    assert first["job"]["index"] == 1
    assert second["workspace"] == "aula"


def test_the_record_keeps_the_prompt_the_provenance_and_the_inputs(stubbed, monkeypatch):
    monkeypatch.setattr(handlers.entrypoints, "generate", _accepting("uno"))
    _run(_job())

    [record] = _records()
    assert record["prompt"] == "prompt de uno"
    assert record["resolved"]["forbidden"] == ["Recursividad"]
    assert record["resolved"]["targets"] == ["Bucles"]
    assert record["resolved"]["item_type"] == "ejercicio"
    assert record["resolved"]["prompt_language"] == "es"
    assert record["output"] == {
        "item": {"enunciado": "uno"},
        "thinking": None,
        "checks": None,
        "retried": 0,
    }
    # The workspace of this test holds no artifact, and says so rather than inventing one.
    assert set(record["inputs"]) >= {
        "exemplars_profile",
        "knowledge_graph",
        "exemplars_bank",
        "content_context",
    }
    assert set(record["inputs"].values()) == {None}
    assert record["settings"]["CHECK_MAX_RETRIES"] is not None


# The level that ran is what the old row lost: it stored `bool(think)`, so "high" and "low"
# read the same, and a level the installation locked was not recorded at all.
def test_the_effort_asked_and_the_effort_that_ran_are_both_kept(stubbed, monkeypatch):
    monkeypatch.setattr(handlers.config, "GENERATION_MODELS", ["el-rapido", "el-fijo"])
    monkeypatch.setattr(handlers.config, "FIXED_EFFORT_MODELS", ["el-fijo"])
    monkeypatch.setattr(handlers.config, "FIXED_EFFORT_LEVELS", {"el-fijo": "medium"})
    monkeypatch.setattr(handlers.entrypoints, "generate", _accepting("uno"))
    _run(_job(think="high", model="el-fijo"))

    [record] = _records()
    assert record["commission"]["think"] == "high"
    assert record["resolved"]["effort"] == "medium"


def test_the_commission_curriculum_is_kept_as_it_was_asked(stubbed, monkeypatch):
    monkeypatch.setattr(
        handlers.curriculum_store,
        "resolve",
        lambda ws, kg, given, student=False: ["Bucles", "Variables"],
    )
    monkeypatch.setattr(handlers.entrypoints, "generate", _accepting("uno"))
    _run(_job())

    [record] = _records()
    assert record["commission"]["curriculum"] is None
    assert record["resolved"]["curriculum"] == ["Bucles", "Variables"]


def test_the_record_names_the_model_the_commission_chose(stubbed, monkeypatch):
    monkeypatch.setattr(handlers.config, "GENERATION_MODELS", ["el-rapido", "el-lento"])
    monkeypatch.setattr(handlers.entrypoints, "generate", _accepting("uno"))
    result, _, error = _run(_job(model="el-lento"))

    assert error is None
    assert result["model"] == "el-lento"
    [record] = _records()
    assert record["commission"]["model"] == "el-lento"
    assert record["resolved"]["model"] == "el-lento"


def test_a_commission_naming_no_model_records_the_default_one(stubbed, monkeypatch):
    monkeypatch.setattr(handlers.config, "GENERATION_MODELS", ["el-rapido", "el-lento"])
    monkeypatch.setattr(handlers.entrypoints, "generate", _accepting("uno"))
    result, _, _ = _run(_job())

    assert result["model"] == "el-rapido"
    [record] = _records()
    assert record["commission"]["model"] is None
    assert record["resolved"]["model"] == "el-rapido"


# The submit route refused it already, so getting here means the offered list changed
# under a job that was waiting: the job fails saying so instead of quietly running on
# whatever the installation offers today.
def test_a_model_that_stopped_being_offered_stops_the_job(stubbed, monkeypatch):
    monkeypatch.setattr(handlers.config, "GENERATION_MODELS", ["el-que-hay"])
    monkeypatch.setattr(handlers.entrypoints, "generate", lambda *a, **k: pytest.fail("no llega"))
    result, _, error = _run(_job(model="el-que-ya-no"))

    assert result is None
    assert isinstance(error, handlers.entrypoints.UnofferedModelError)
    assert _records() == []


def test_a_cancelled_run_keeps_what_it_validated(stubbed, monkeypatch):
    def fake_generate(context, **kwargs):
        kwargs["on_accepted"](_variant("uno"), 1)
        kwargs["on_accepted"](_variant("dos"), 2)
        raise Cancelled("cancelled by the user")

    monkeypatch.setattr(handlers.entrypoints, "generate", fake_generate)
    result, _, error = _run(_job(n=5))

    assert result is None and isinstance(error, Cancelled)
    assert [store.item_of(r)["enunciado"] for r in _records()] == ["uno", "dos"]


def test_a_disk_failure_loses_the_record_and_nothing_else(stubbed, monkeypatch):
    def full_disk(*args, **kwargs):
        raise OSError("No queda espacio en el dispositivo")

    monkeypatch.setattr(handlers.generations_store, "save", full_disk)
    monkeypatch.setattr(handlers.entrypoints, "generate", _accepting("uno"))
    result, emitter, error = _run(_job())

    assert error is None
    assert result["produced"] == 1 and result["saved"] == 0
    assert result["items"][0]["saved_id"] is None
    assert not [k for k, _ in emitter.events if k == "item.saved"]


def test_two_accounts_write_to_two_directories(stubbed, monkeypatch):
    monkeypatch.setattr(handlers.entrypoints, "generate", _accepting("de Ana"))
    _run(_job())
    monkeypatch.setattr(handlers.entrypoints, "generate", _accepting("de Luis"))
    _run(Job(kind="generate", params={"concepts": ["Bucles"]}, workspace="aula", user_id=8))

    assert [store.item_of(r)["enunciado"] for r in _records(7)] == ["de Ana"]
    assert [store.item_of(r)["enunciado"] for r in _records(8)] == ["de Luis"]


# `or 1` was wrong on a falsy zero: a commission of "generate 0 items" produced one and then
# reported `requested: 1`, so the record kept a commission nobody made. An absent `n` still
# means one; a zero has to reach the generator, which is what refuses it.
def test_a_count_of_zero_is_not_silently_turned_into_one(stubbed, monkeypatch):
    seen = {}

    def fake_generate(context, **kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(handlers.entrypoints, "generate", fake_generate)
    result, _, error = _run(_job(n=0))

    assert error is None
    assert seen["n"] == 0
    assert result["requested"] == 0
    assert not _records()


def test_an_absent_count_still_means_one(stubbed, monkeypatch):
    seen = {}

    def fake_generate(context, **kwargs):
        seen.update(kwargs)
        kwargs["on_accepted"](_variant("uno"), 1)
        return [_variant("uno")]

    monkeypatch.setattr(handlers.entrypoints, "generate", fake_generate)
    job = Job(kind="generate", params={"concepts": ["Bucles"]}, workspace="aula", user_id=7)
    result, _, error = _run(job)

    assert error is None
    assert seen["n"] == 1
    assert result["requested"] == 1
    assert _records()[0]["job"]["requested"] == 1


def test_the_parts_a_commission_leaves_out_reach_the_generator_and_the_file(stubbed, monkeypatch):
    seen: dict = {}

    def fake_generate(context, **kwargs):
        seen.update(kwargs)
        return _accepting("uno")(context, **kwargs)

    monkeypatch.setattr(handlers.entrypoints, "generate", fake_generate)
    _run(_job(omit=["solucion"]))
    assert seen["omit"] == ["solucion"]
    assert _records()[0]["commission"]["omit"] == ["solucion"]


def test_a_commission_that_leaves_nothing_out_says_so(stubbed, monkeypatch):
    seen: dict = {}

    def fake_generate(context, **kwargs):
        seen.update(kwargs)
        return _accepting("uno")(context, **kwargs)

    monkeypatch.setattr(handlers.entrypoints, "generate", fake_generate)
    _run(_job())
    assert seen["omit"] is None
    assert _records()[0]["commission"]["omit"] == []
