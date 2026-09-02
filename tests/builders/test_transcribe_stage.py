import pytest

from variatio import config
from variatio.builders._source_docs import pages
from variatio.core.workspace import Workspace
from variatio.stages import transcribe


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path, "pruebas")
    workspace.raw_corpus_dir.mkdir(parents=True)
    workspace.raw_exemplars_dir.mkdir(parents=True)
    return workspace


def document(ws: Workspace, slot: str, name: str, text: str = "una pregunta"):
    source = transcribe.slot_dir(ws, slot) / name
    source.write_text(text, encoding="utf-8")
    return source


def transcribed(ws: Workspace, slot: str, name: str, text: str = "una pregunta"):
    source = document(ws, slot, name, text)
    transcribe.transcribe_slot(ws, slot)
    return source


def cache_of(ws: Workspace, source):
    return pages.document_cache_dir(source, ws.markdown_cache_dir)


# THE SLOTS ---------------------------------------------------------------------------------------


def test_the_two_slots_map_to_the_two_raw_directories(ws):
    assert transcribe.slot_dir(ws, "corpus") == ws.raw_corpus_dir
    assert transcribe.slot_dir(ws, "exemplars") == ws.raw_exemplars_dir


def test_an_unknown_slot_is_refused(ws):
    with pytest.raises(ValueError):
        transcribe.slot_dir(ws, "otro")


def test_a_missing_raw_directory_is_an_empty_slot_and_not_a_crash(tmp_path):
    empty = Workspace(tmp_path, "vacio")
    assert transcribe.transcription_status(empty, "corpus")["documents"] == []


# THE THREE STATES --------------------------------------------------------------------------------


def test_a_document_never_transcribed_is_pending(ws):
    document(ws, "corpus", "apuntes.md")
    status = transcribe.transcription_status(ws, "corpus")
    assert status["pending"] == 1
    assert status["done"] == 0
    assert status["documents"][0]["state"] == "pending"
    assert status["documents"][0]["reasons"] == []


def test_a_transcribed_document_is_done_and_counts_its_pages(ws):
    transcribed(ws, "corpus", "apuntes.md", "una pregunta")
    status = transcribe.transcription_status(ws, "corpus")
    assert status["done"] == 1
    assert status["total_pages"] == 1
    document_status = status["documents"][0]
    assert document_status["state"] == "done"
    assert document_status["chars"] > 0
    assert document_status["failed_pages"] == 0


def test_a_changed_configuration_makes_it_stale_and_says_what_changed(ws):
    source = transcribed(ws, "corpus", "apuntes.md")
    meta = pages.read_meta(cache_of(ws, source))
    pages.write_pages(
        cache_of(ws, source),
        pages.read_pages(cache_of(ws, source)),
        {**pages.fingerprint_of(meta), "prompt_version": 99, "dpi": 12},
    )
    status = transcribe.transcription_status(ws, "corpus")
    assert status["stale"] == 1
    assert status["documents"][0]["state"] == "stale"
    assert set(status["documents"][0]["reasons"]) == {"prompt", "dpi"}


def test_a_changed_document_is_stale_because_of_the_document(ws):
    source = transcribed(ws, "corpus", "apuntes.md", "una pregunta")
    source.write_text("otra pregunta muy distinta", encoding="utf-8")
    assert transcribe.transcription_status(ws, "corpus")["documents"][0]["reasons"] == [
        "document"
    ]


def test_the_status_reads_no_model_and_survives_an_engine_that_is_not_there(ws, monkeypatch):
    def boom(**_kwargs):
        raise AssertionError("el estado no puede llamar a ningún modelo")

    monkeypatch.setattr(pages.inference, "generate", boom)
    transcribed(ws, "exemplars", "examen.md")
    assert transcribe.transcription_status(ws, "exemplars")["done"] == 1


def test_the_two_slots_do_not_see_each_other(ws):
    transcribed(ws, "corpus", "apuntes.md")
    assert transcribe.transcription_status(ws, "exemplars")["documents"] == []


# TRANSCRIBING ------------------------------------------------------------------------------------


def test_transcribing_reports_what_it_did(ws):
    document(ws, "corpus", "apuntes.md")
    summary = transcribe.transcribe_slot(ws, "corpus")
    assert summary == {
        "slot": "corpus",
        "documents": 1,
        "pages": 1,
        "seams_merged": 0,
        "failed_pages": 0,
        "images": 0,
        "images_unreadable": 0,
    }


def test_an_empty_slot_transcribes_nothing_and_does_not_raise(ws):
    assert transcribe.transcribe_slot(ws, "corpus")["documents"] == 0


def test_a_second_run_reuses_the_cache_and_keeps_a_hand_edit(ws):
    source = transcribed(ws, "corpus", "apuntes.md")
    (cache_of(ws, source) / "001.md").write_text("corregido a mano", encoding="utf-8")
    transcribe.transcribe_slot(ws, "corpus")
    assert pages.read_pages(cache_of(ws, source)) == ["corregido a mano"]


# HAND EDITING ------------------------------------------------------------------------------------


def three_pages(ws):
    source = transcribed(ws, "exemplars", "examen.md")
    cache = cache_of(ws, source)
    meta = pages.read_meta(cache)
    pages.write_pages(
        cache,
        ["Uno.", "Dos.", "Tres."],
        pages.fingerprint_of(meta),
        [{"page": 2, "separator": "space"}, {"page": 3, "separator": "space"}],
    )
    return source, cache


def test_the_listing_numbers_the_pages_from_one(ws):
    three_pages(ws)
    listing = transcribe.document_pages_listing(ws, "exemplars", "examen.md")
    assert [page["index"] for page in listing] == [1, 2, 3]
    assert [page["text"] for page in listing] == ["Uno.", "Dos.", "Tres."]
    assert all(not page["failed"] for page in listing)


def test_a_document_with_no_cache_lists_nothing(ws):
    document(ws, "exemplars", "examen.md")
    assert transcribe.document_pages_listing(ws, "exemplars", "examen.md") == []


def test_an_unknown_document_is_refused(ws):
    with pytest.raises(ValueError):
        transcribe.document_pages_listing(ws, "exemplars", "../../etc/passwd")


def test_writing_a_page_keeps_the_fingerprint_so_the_edit_survives(ws):
    source, cache = three_pages(ws)
    before = pages.fingerprint_of(pages.read_meta(cache))
    transcribe.write_document_page(ws, "exemplars", "examen.md", 2, "Corregido.")
    assert pages.read_pages(cache) == ["Uno.", "Corregido.", "Tres."]
    assert pages.fingerprint_of(pages.read_meta(cache)) == before
    assert pages.read_meta(cache)["pages"] == 3


def test_writing_a_page_drops_only_the_seams_it_touches(ws):
    _source, cache = three_pages(ws)
    transcribe.write_document_page(ws, "exemplars", "examen.md", 3, "Corregido.")
    assert [record["page"] for record in pages.read_meta(cache)["seams"]] == [2]


def test_inserting_renumbers_and_leaves_no_orphan_file(ws):
    _source, cache = three_pages(ws)
    index = transcribe.insert_document_page(ws, "exemplars", "examen.md", 1, "Nueva.")
    assert index == 2
    assert pages.read_pages(cache) == ["Uno.", "Nueva.", "Dos.", "Tres."]
    assert sorted(p.name for p in cache.iterdir()) == [
        "001.md",
        "002.md",
        "003.md",
        "004.md",
        "_meta.json",
    ]


def test_inserting_at_the_beginning_is_allowed(ws):
    _source, cache = three_pages(ws)
    assert transcribe.insert_document_page(ws, "exemplars", "examen.md", 0, "Cero.") == 1
    assert pages.read_pages(cache)[0] == "Cero."


def test_inserting_past_the_end_is_refused(ws):
    three_pages(ws)
    with pytest.raises(ValueError):
        transcribe.insert_document_page(ws, "exemplars", "examen.md", 9, "Nueva.")


def test_deleting_renumbers_and_leaves_no_orphan_file(ws):
    _source, cache = three_pages(ws)
    transcribe.delete_document_page(ws, "exemplars", "examen.md", 2)
    assert pages.read_pages(cache) == ["Uno.", "Tres."]
    assert sorted(p.name for p in cache.iterdir()) == ["001.md", "002.md", "_meta.json"]
    assert pages.read_meta(cache)["pages"] == 2


def test_deleting_the_only_page_is_refused(ws):
    source = transcribed(ws, "exemplars", "examen.md")
    assert len(pages.read_pages(cache_of(ws, source))) == 1
    with pytest.raises(ValueError):
        transcribe.delete_document_page(ws, "exemplars", "examen.md", 1)


def test_a_page_that_does_not_exist_is_refused(ws):
    three_pages(ws)
    for call in (
        lambda: transcribe.write_document_page(ws, "exemplars", "examen.md", 0, "x"),
        lambda: transcribe.write_document_page(ws, "exemplars", "examen.md", 4, "x"),
        lambda: transcribe.delete_document_page(ws, "exemplars", "examen.md", 4),
    ):
        with pytest.raises(ValueError):
            call()


def test_an_edited_document_still_reads_as_done(ws):
    three_pages(ws)
    transcribe.write_document_page(ws, "exemplars", "examen.md", 1, "Corregido.")
    status = transcribe.transcription_status(ws, "exemplars")
    assert status["done"] == 1
    assert status["total_pages"] == 3


def test_a_failed_page_is_reported_as_such(ws):
    _source, cache = three_pages(ws)
    transcribe.write_document_page(
        ws, "exemplars", "examen.md", 2, f"{pages.FAILED_PAGE_PREFIX} — página 2 de 3]"
    )
    listing = transcribe.document_pages_listing(ws, "exemplars", "examen.md")
    assert [page["failed"] for page in listing] == [False, True, False]
    assert transcribe.transcription_status(ws, "exemplars")["documents"][0]["failed_pages"] == 1


def test_the_corpus_slot_never_asks_for_ocr(ws):
    assert transcribe._slot_ocr("corpus") is False
    assert transcribe._slot_ocr("exemplars") is config.EXEMPLARS_OCR


# THE PICTURES OF AN OFFICE DOCUMENT ---------------------------------------------------------------


def test_the_status_reports_the_pictures_a_document_lost(ws):
    # A picture Docling could not open leaves a mark in the page and a count on the row:
    # loss has to be visible, or it is not a state anyone can act on.
    source = transcribed(ws, "corpus", "apuntes.md")
    meta = pages.read_meta(cache_of(ws, source))
    pages.write_pages(
        cache_of(ws, source),
        pages.read_pages(cache_of(ws, source)),
        pages.fingerprint_of(meta),
        images={"images_total": 3, "images_unreadable": 2},
    )

    row = transcribe.transcription_status(ws, "corpus")["documents"][0]
    assert row["state"] == "done"
    assert row["images"] == 3 and row["images_unreadable"] == 2


def test_a_meta_written_before_the_pictures_reports_none(ws):
    source = transcribed(ws, "corpus", "apuntes.md")
    row = transcribe.transcription_status(ws, "corpus")["documents"][0]
    assert row["images"] == 0 and row["images_unreadable"] == 0
    assert transcribe.transcription_status(ws, "corpus")["documents"][0]["state"] == "done"
