"""What shapes the picture the model is sent is part of a page's fingerprint, by route.

The values were constants until 2026-10-02 and entered the fingerprint then; a meta written
before reads as made with those values, so recording them expired nothing.
"""

from variatio import config
from variatio.builders.source_docs import pages
from variatio.core import repetition
from variatio.entrypoints import transcribe


def test_the_defaults_are_the_values_every_older_page_was_read_with():
    for mode in ("vlm", "docling"):
        record = pages._render_record(mode)
        assert record == {key: pages.RENDER_BEFORE[key] for key in record}, mode


def test_a_meta_written_before_the_render_fields_reads_as_current():
    old = {"mode": "vlm", "model": "m", "dpi": 200, "ocr": False, "temperature": 0.0}
    stored = pages.fingerprint_of({**old, "pages": 3})
    expected = {**old, **pages._render_record("vlm")}
    assert pages.same_document(stored, expected)


def test_a_moved_render_field_expires_the_page_and_is_named(monkeypatch):
    old = {"mode": "vlm", "model": "m", "dpi": 200, "ocr": False, "temperature": 0.0}
    stored = pages.fingerprint_of(old)
    monkeypatch.setattr(config, "TRANSCRIBE_PAGE_JPEG_QUALITY", 70)
    expected = {**old, **pages._render_record("vlm")}
    assert not pages.same_document(stored, expected)
    assert transcribe._reasons(stored, expected) == ["render"]


def test_the_pictures_route_records_the_picture_fields_and_not_the_page_render():
    record = pages._render_record("docling")
    assert "raster_scale" in record and "picture_min_side" in record
    assert "render_max_a4" not in record


def test_a_loop_verdict_follows_the_thresholds_in_force(monkeypatch):
    page = "| | |\n" * 30
    assert pages._holds_loop(page)
    monkeypatch.setattr(config, "TRANSCRIBE_LOOP_LINES", 100)
    monkeypatch.setattr(config, "TRANSCRIBE_LOOP_CHARS", 10_000)
    assert repetition.detect(page) is None
    assert not pages._holds_loop(page)
