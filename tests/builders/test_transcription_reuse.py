"""A document already transcribed anywhere in the installation is not transcribed again.

Identity is the file's BYTES, which is what `_page_fingerprint` already says: the same PDF
uploaded into two subjects, or into one subject twice under two names, is one document, and
its pages carry over as a filesystem copy instead of one model call per page.

What the tests pin is the boundary of that shortcut. It fires on the bytes and the settings
together and on nothing less: a document whose content differs, or whose pages were produced
under a model, a DPI, a prompt version or an OCR flag that no longer applies, is transcribed
and not adopted. The COPY is what is pinned rather than a link — a hand correction on either
side must not rewrite the other.
"""

import pytest

from variatio.builders.source_docs import pages
from variatio.core import paths
from variatio.core.workspace import Workspace
from variatio.entrypoints import transcribe

TEXT = "Un enunciado que ocupa una página entera."


@pytest.fixture
def workspaces(tmp_path):
    """Two subjects of the SAME installation: direct children of `WORKSPACES_DIR`.

    The scan globs `workspaces/*/cache/markdown/*/*/_meta.json`, which is a statement about
    the tree's shape, so a fixture that nested them one level deeper would pin nothing. The
    slugs carry the test's own name because `WORKSPACES_DIR` is session-scoped.
    """
    made = []
    for slug in (f"{tmp_path.name}-uno", f"{tmp_path.name}-dos"):
        ws = Workspace(paths.WORKSPACES_DIR / slug, slug)
        ws.raw_corpus_dir.mkdir(parents=True, exist_ok=True)
        ws.raw_exemplars_dir.mkdir(parents=True, exist_ok=True)
        made.append(ws)
    return tuple(made)


def put(ws: Workspace, slot: str, name: str, text: str = TEXT):
    source = transcribe.slot_dir(ws, slot) / name
    source.write_text(text, encoding="utf-8")
    return source


def cache_of(ws: Workspace, source):
    return pages.document_cache_dir(source, ws.markdown_cache_dir)


# THE KEY -----------------------------------------------------------------------------------------


def test_the_reuse_key_drops_the_name_and_keeps_everything_else():
    here = {"source": "apuntes.pdf", "source_sha256": "abc", "mode": "vlm", "dpi": 200}
    there = {**here, "source": "tema-1.pdf"}
    assert pages.reuse_key(here) == pages.reuse_key(there)
    assert pages.reuse_key(here) != pages.reuse_key({**here, "source_sha256": "otro"})
    assert pages.reuse_key(here) != pages.reuse_key({**here, "dpi": 300})


# ADOPTING ----------------------------------------------------------------------------------------


def test_the_same_document_in_another_subject_is_adopted_whole(workspaces):
    uno, dos = workspaces
    donor = put(uno, "corpus", "apuntes.md")
    transcribe.transcribe_slot(uno, "corpus")
    assert transcribe.transcription_status(uno, "corpus")["done"] == 1

    taker = put(dos, "corpus", "apuntes.md")
    assert transcribe.transcription_status(dos, "corpus")["pending"] == 1

    report = transcribe.adopt_transcriptions(dos, "corpus")
    assert report == {"adopted": 1, "pages": 1}
    assert transcribe.transcription_status(dos, "corpus")["done"] == 1
    assert pages.read_pages(cache_of(dos, taker)) == pages.read_pages(cache_of(uno, donor))


def test_the_same_bytes_under_another_name_are_the_same_document(workspaces):
    uno, dos = workspaces
    put(uno, "corpus", "tema-1.md")
    transcribe.transcribe_slot(uno, "corpus")

    put(dos, "corpus", "copia-del-tema.md")
    assert transcribe.adopt_transcriptions(dos, "corpus")["adopted"] == 1


def test_a_different_document_is_not_adopted(workspaces):
    uno, dos = workspaces
    put(uno, "corpus", "apuntes.md")
    transcribe.transcribe_slot(uno, "corpus")

    put(dos, "corpus", "apuntes.md", text="Otro enunciado distinto.")
    assert transcribe.adopt_transcriptions(dos, "corpus")["adopted"] == 0
    assert transcribe.transcription_status(dos, "corpus")["pending"] == 1


def test_a_document_already_read_is_left_alone(workspaces):
    uno, _ = workspaces
    source = put(uno, "corpus", "apuntes.md")
    transcribe.transcribe_slot(uno, "corpus")
    before = pages.read_meta(cache_of(uno, source))

    assert transcribe.adopt_transcriptions(uno, "corpus") == {"adopted": 0, "pages": 0}
    assert pages.read_meta(cache_of(uno, source)) == before


def test_settings_that_moved_are_not_adopted_over(workspaces, monkeypatch):
    """A donor read at another temperature is stale, not a shortcut."""
    uno, dos = workspaces
    put(uno, "corpus", "apuntes.md")
    transcribe.transcribe_slot(uno, "corpus")

    from variatio import config

    monkeypatch.setattr(config, "TRANSCRIBE_TEMPERATURE", config.TRANSCRIBE_TEMPERATURE + 0.5)
    put(dos, "corpus", "apuntes.md")
    assert transcribe.adopt_transcriptions(dos, "corpus")["adopted"] == 0


def test_the_pages_are_copied_and_not_shared(workspaces):
    """Correcting one side leaves the other exactly as it was."""
    uno, dos = workspaces
    donor = put(uno, "corpus", "apuntes.md")
    transcribe.transcribe_slot(uno, "corpus")
    original = pages.read_pages(cache_of(uno, donor))
    taker = put(dos, "corpus", "apuntes.md")
    transcribe.adopt_transcriptions(dos, "corpus")
    assert pages.read_pages(cache_of(dos, taker)) == original

    transcribe.write_document_page(dos, "corpus", "apuntes.md", 1, "Corregido a mano.")
    assert pages.read_pages(cache_of(dos, taker)) == ["Corregido a mano."]
    assert pages.read_pages(cache_of(uno, donor)) == original


def test_a_slot_transcription_adopts_before_it_reads_anything(workspaces):
    """The job is where a document uploaded before this existed catches up."""
    uno, dos = workspaces
    put(uno, "exemplars", "examen.md")
    transcribe.transcribe_slot(uno, "exemplars")

    put(dos, "exemplars", "examen.md")
    transcribe.transcribe_slot(dos, "exemplars")
    assert transcribe.transcription_status(dos, "exemplars")["done"] == 1
