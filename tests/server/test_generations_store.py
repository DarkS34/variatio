"""The generated exercises as files: one per exercise, under its author, never shared.

The id comes from a request and is joined to a path, so it is checked on every read; four
jobs of one workspace may write at once, so no two writes share a file; and one damaged
file is skipped, never the reason a listing comes back empty.
"""

import threading
from datetime import datetime, timedelta, timezone

import pytest

from server import generations as store
from server.cli.generations import legacy_record
from variatio.core.workspace import Workspace

MOMENT = datetime(2026, 10, 1, 10, 15, 30, tzinfo=timezone.utc)


@pytest.fixture
def ws(tmp_path):
    return Workspace(tmp_path / "aula", slug="aula")


def _body(text: str, concepts=("Bucles",), item_type: str = "ejercicio") -> dict:
    return {
        "workspace": "aula",
        "commission": {"concepts": list(concepts), "instructions": None},
        "resolved": {"targets": list(concepts), "item_type": item_type},
        "output": {"item": {"enunciado": text}},
    }


def _save(ws, user_id, text, index=1, job="abc123", when=MOMENT, **kwargs) -> str:
    return store.save(ws, user_id, job, index, _body(text, **kwargs), now=when)


# WHERE A RECORD LIVES ----------------------------------------------------------------------------


def test_an_exercise_is_one_file_under_its_author(ws):
    generation_id = _save(ws, 7, "uno", index=3)

    assert generation_id == "20261001T101530Z-abc123-3"
    path = ws.generations_dir / "user_7" / f"{generation_id}.json"
    assert path.is_file()
    record = store.get(ws, 7, generation_id)
    assert record["format"] == store.FORMAT
    assert record["created_at"] == "2026-10-01T10:15:30Z"
    assert record["promoted_item_id"] is None


def test_a_record_without_an_author_goes_to_the_orphaned_directory(ws):
    generation_id = _save(ws, None, "nadie")

    assert (ws.generations_dir / store.ORPHANED / f"{generation_id}.json").is_file()


def test_another_accounts_id_reads_as_nothing(ws):
    generation_id = _save(ws, 7, "mío")

    assert store.get(ws, 8, generation_id) is None
    assert store.delete(ws, 8, generation_id) is False
    assert store.get(ws, 7, generation_id) is not None


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "..",
        "../8/20261001T101530Z-abc123-1",
        "20261001T101530Z-abc123-1.json",
        "20261001T101530Z-abc123-1\n",
        "/etc/passwd",
        "20261001T101530Z-ABC-1",
        "x" * 300,
    ],
)
def test_a_malformed_id_never_reaches_the_filesystem(ws, bad):
    _save(ws, 8, "suyo")

    assert store.get(ws, 7, bad) is None
    assert store.delete(ws, 7, bad) is False


def test_writing_refuses_an_id_the_store_would_never_read(ws):
    with pytest.raises(ValueError):
        store.write(ws, 7, {"id": "../../fuera"})
    assert not (ws.root.parent / "fuera.json").exists()


def test_concurrent_runs_of_one_account_lose_nothing(ws):
    """The remote lane runs up to four jobs of one workspace at once."""
    errors: list[BaseException] = []

    def run(job: str) -> None:
        try:
            for index in range(1, 26):
                _save(ws, 7, f"{job}-{index}", index=index, job=job)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(f"job{n}",)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    records, total = store.list_for(ws, 7, limit=1000)
    assert total == 100
    assert len({r["id"] for r in records}) == 100
    assert not list(ws.generations_dir.rglob("*.tmp"))


# READING -----------------------------------------------------------------------------------------


def test_the_listing_is_newest_first_and_in_batch_order_within_a_second(ws):
    _save(ws, 7, "viejo", when=MOMENT - timedelta(minutes=1))
    for index in (1, 2, 10):
        _save(ws, 7, f"tanda {index}", index=index)

    records, total = store.list_for(ws, 7)

    assert total == 4
    assert [store.item_of(r)["enunciado"] for r in records] == [
        "tanda 10",
        "tanda 2",
        "tanda 1",
        "viejo",
    ]


def test_the_listing_filters_by_concept_modality_and_text(ws):
    _save(ws, 7, "sobre bucles", index=1)
    _save(ws, 7, "sobre listas", index=2, concepts=("Listas",))
    _save(ws, 7, "otra modalidad", index=3, item_type="analisis")

    def texts(**filters):
        records, _ = store.list_for(ws, 7, **filters)
        return [store.item_of(r)["enunciado"] for r in records]

    assert texts(concept="Listas") == ["sobre listas"]
    assert texts(item_type="analisis") == ["otra modalidad"]
    assert texts(query="BUCLES") == ["otra modalidad", "sobre bucles"]
    records, total = store.list_for(ws, 7, limit=1, offset=1)
    assert total == 3 and len(records) == 1


def test_an_unreadable_file_is_skipped_and_said_once(ws, caplog):
    from loguru import logger

    _save(ws, 7, "sano")
    (ws.generations_dir / "user_7" / "20261001T101531Z-roto-1.json").write_text("{ no es json")
    messages: list[str] = []
    sink = logger.add(lambda message: messages.append(str(message)), level="WARNING")
    try:
        first, _ = store.list_for(ws, 7)
        second, _ = store.list_for(ws, 7)
    finally:
        logger.remove(sink)

    assert [store.item_of(r)["enunciado"] for r in first] == ["sano"]
    assert [store.item_of(r)["enunciado"] for r in second] == ["sano"]
    assert len([m for m in messages if "ilegible" in m]) == 1


def test_counts_are_per_workspace_and_per_author(ws, tmp_path):
    other = Workspace(tmp_path / "otra", slug="otra")
    _save(ws, 7, "a", index=1)
    _save(ws, 7, "b", index=2)
    _save(ws, 8, "c")
    _save(ws, None, "huérfano")
    _save(other, 7, "d")
    for stray in ("user_x", "7", "notas"):
        (ws.generations_dir / stray).mkdir()

    assert sorted(p.name for p in ws.generations_dir.iterdir() if any(p.iterdir())) == [
        "_orphaned",
        "user_7",
        "user_8",
    ]
    assert store.count(ws) == 4
    assert store.count(Workspace(tmp_path / "vacía", slug="vacia")) == 0
    assert store.count_by_author([ws, other]) == {7: 3, 8: 1}
    assert (store.count_for(ws, 7), store.count_for(other, 7), store.count_for(ws, 9)) == (2, 1, 0)


def test_promoting_rewrites_the_record_in_place(ws):
    generation_id = _save(ws, 7, "uno")
    record = store.get(ws, 7, generation_id)

    store.mark_promoted(ws, 7, record, "C042")

    assert store.get(ws, 7, generation_id)["promoted_item_id"] == "C042"
    assert len(list((ws.generations_dir / "user_7").glob("*.json"))) == 1


# A ROW OF THE RETIRED TABLE ----------------------------------------------------------------------


def _row(**overrides) -> dict:
    row = {
        "id": 17,
        "workspace_id": 1,
        "workspace_slug": "aula",
        "user_id": 7,
        "author_username": "ana",
        "author_name": "Ana",
        "job_id": "abc123",
        "item_type": "ejercicio",
        "concepts": [],
        "curriculum": ["Bucles", "Variables"],
        "fixed": {"nivel_dificultad": "basico"},
        "instructions": "de cocina",
        "think": True,
        "model": "qwen",
        "item": {"enunciado": "heredado"},
        "thinking": "pensé",
        "checks": {"flags": []},
        "promoted_item_id": None,
        "created_at": MOMENT,
    }
    return {**row, **overrides}


def test_a_legacy_row_keeps_what_the_table_kept_and_invents_nothing(ws):
    record = legacy_record(_row())
    store.write(ws, 7, record)

    read = store.get(ws, 7, "20261001T101530Z-db17")
    assert read["format"] == store.LEGACY_FORMAT
    assert read["legacy_id"] == 17
    assert read["commission"]["think"] is True
    assert read["commission"]["model"] is None
    assert read["resolved"]["model"] == "qwen"
    assert read["resolved"]["curriculum"] == ["Bucles", "Variables"]
    assert read["resolved"]["targets"] is None
    assert read["resolved"]["few_shot"] is None
    assert read["prompt"] is None and read["inputs"] is None
    assert store.item_type_of(read) == "ejercicio"
    assert store.item_of(read) == {"enunciado": "heredado"}


def test_a_legacy_row_reads_beside_the_new_ones(ws):
    store.write(ws, 7, legacy_record(_row(created_at=MOMENT - timedelta(days=1))))
    _save(ws, 7, "nuevo")

    records, _ = store.list_for(ws, 7)
    assert [store.item_of(r)["enunciado"] for r in records] == ["nuevo", "heredado"]


def test_a_naive_timestamp_from_sqlite_is_read_as_utc():
    record = legacy_record(_row(created_at=MOMENT.replace(tzinfo=None)))

    assert record["id"] == "20261001T101530Z-db17"
    assert record["created_at"] == "2026-10-01T10:15:30Z"
