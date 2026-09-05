import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from variatio.builders.source_docs import pages
from variatio.core import progress

from ..conftest import ES

PAGES = ["primera página", "segunda página", "tercera página", "cuarta página"]
TIDIED = [page + "\n" for page in PAGES]


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "raw" / "raw_corpus" / "apuntes.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-fake")
    return path


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "markdown"


def _images(monkeypatch, count: int = len(PAGES)) -> None:
    monkeypatch.setattr(
        pages,
        "page_images",
        lambda path, dpi, first=1: (count, iter(range(first - 1, count))),
    )


def _model(monkeypatch, stop_at: int | None = None) -> list[int]:
    """Records the page indices actually asked for. `stop_at` cancels just before one."""
    asked: list[int] = []

    def transcribe_page(image, index, count, model, tag, prompts):
        if stop_at is not None and index >= stop_at:
            raise progress.Cancelled("cancelled by the user")
        asked.append(index)
        return PAGES[index - 1]

    monkeypatch.setattr(pages, "_transcribe_page", transcribe_page)
    monkeypatch.setattr(
        pages.inference,
        "generate",
        lambda **kwargs: SimpleNamespace(
            response=json.dumps(
                {"continues": False, "separator": "paragraph", "drop_head_lines": 0}
            )
        ),
    )
    return asked


def _cancelled_after_two(source, cache, monkeypatch) -> Path:
    _images(monkeypatch)
    _model(monkeypatch, stop_at=3)
    with pytest.raises(progress.Cancelled):
        pages.document_pages(source, ES, cache_dir=cache)
    return pages.document_cache_dir(source, cache)


def test_a_cancelled_transcription_keeps_the_pages_it_already_paid_for(
    source, cache, monkeypatch
):
    document = _cancelled_after_two(source, cache, monkeypatch)

    assert (document / "001.md").read_text(encoding="utf-8") == PAGES[0]
    assert (document / "002.md").read_text(encoding="utf-8") == PAGES[1]
    assert not (document / "003.md").exists()
    assert (document / pages.PARTIAL_NAME).exists()


def test_an_interrupted_document_is_never_read_back_as_a_finished_one(
    source, cache, monkeypatch
):
    document = _cancelled_after_two(source, cache, monkeypatch)

    assert not (document / pages.META_NAME).exists()
    assert pages.read_meta(document) == {}
    assert pages.read_pages(document) == []


def test_relaunching_asks_the_model_only_for_the_pages_that_are_missing(
    source, cache, monkeypatch
):
    _cancelled_after_two(source, cache, monkeypatch)

    _images(monkeypatch)
    asked = _model(monkeypatch)
    result = pages.document_pages(source, ES, cache_dir=cache)

    assert asked == [3, 4]
    assert result == TIDIED


def test_finishing_the_document_clears_the_partial_marker(source, cache, monkeypatch):
    document = _cancelled_after_two(source, cache, monkeypatch)

    _images(monkeypatch)
    _model(monkeypatch)
    pages.document_pages(source, ES, cache_dir=cache)

    assert not (document / pages.PARTIAL_NAME).exists()
    assert (document / pages.META_NAME).exists()
    assert pages.read_pages(document) == TIDIED


def test_a_partial_written_under_other_settings_is_not_resumed(source, cache, monkeypatch):
    document = _cancelled_after_two(source, cache, monkeypatch)

    marker_path = document / pages.PARTIAL_NAME
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["fingerprint"]["model"] = "otro-modelo"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")

    _images(monkeypatch)
    asked = _model(monkeypatch)
    pages.document_pages(source, ES, cache_dir=cache)

    assert asked == [1, 2, 3, 4]


def test_a_partial_missing_its_pages_falls_back_to_transcribing_them(
    source, cache, monkeypatch
):
    document = _cancelled_after_two(source, cache, monkeypatch)
    (document / "002.md").unlink()

    _images(monkeypatch)
    asked = _model(monkeypatch)
    result = pages.document_pages(source, ES, cache_dir=cache)

    assert asked == [2, 3, 4]
    assert result == TIDIED


def test_a_finished_document_still_costs_no_call_at_all(source, cache, monkeypatch):
    _images(monkeypatch)
    _model(monkeypatch)
    pages.document_pages(source, ES, cache_dir=cache)

    _images(monkeypatch)
    asked = _model(monkeypatch)
    result = pages.document_pages(source, ES, cache_dir=cache)

    assert asked == []
    assert result == TIDIED
