"""The speaker notes of a PowerPoint deck are read and quoted under their slide.

Docling never opens `notes_slide`, and on the reference decks that is where the teacher put
the explanation — 69 of one deck's 103 slides carried 41 000 characters of notes against
36 000 of slide text. The notes are the author's own text, read straight off the file with
python-pptx and put under the slide they belong to; what is pinned here is the placement,
the escape rule, the fingerprint and that a document with no notes is byte for byte what
it was.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from variatio.builders.source_docs import office, pages
from variatio.core import inference
from variatio.wording import en as EN_WORDING
from variatio.wording import es as ES_WORDING

from ..conftest import ES

docling = pytest.importorskip("docling_core.types.doc")
pptx = pytest.importorskip("pptx")


def _deck(path: Path, notes: dict[int, str], slides: int = 3) -> Path:
    """Write a deck of `slides` slides, with `notes` on the ones named."""
    presentation = pptx.Presentation()
    for number in range(1, slides + 1):
        slide = presentation.slides.add_slide(presentation.slide_layouts[5])
        slide.shapes.title.text = f"Diapositiva {number}"
        if number in notes:
            slide.notes_slide.notes_text_frame.text = notes[number]
    path.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(str(path))
    return path


def _prov(page: int):
    return docling.ProvenanceItem(
        page_no=page, bbox=docling.BoundingBox(l=0, t=0, r=1, b=1), charspan=(0, 0)
    )


def _document(slides: int = 3):
    """What Docling makes of such a deck: one page per slide, every item naming its slide."""
    doc = docling.DoclingDocument(name="t")
    for number in range(1, slides + 1):
        doc.add_page(page_no=number, size=docling.Size(width=10, height=10))
        doc.add_text(
            label=docling.DocItemLabel.SECTION_HEADER,
            text=f"Diapositiva {number}",
            prov=_prov(number),
        )
        doc.add_text(
            label=docling.DocItemLabel.PARAGRAPH, text=f"texto {number}", prov=_prov(number)
        )
    return doc


def _converter(document):
    return SimpleNamespace(convert=lambda path: SimpleNamespace(document=document))


def _read(source: Path, prompts=ES, document=None) -> str:
    """The deck as one string, its pages joined by a blank line."""
    return "\n".join(_pages(source, prompts, document))


def _pages(source: Path, prompts=ES, document=None) -> list[str]:
    read, _ = pages.transcribe_office(source, _converter(document or _document()), "m", prompts)
    return read


def test_a_deck_is_one_page_per_slide_with_the_note_under_its_own(tmp_path):
    source = _deck(tmp_path / "raw" / "raw_corpus" / "tema.pptx", {2: "lo que explica el profesor"})

    assert _pages(source) == [
        "## Diapositiva 1\n\ntexto 1\n",
        "## Diapositiva 2\n\ntexto 2\n\n> **Notas del orador**\n>\n> lo que explica el profesor\n",
        "## Diapositiva 3\n\ntexto 3\n",
    ]


def test_a_slide_with_nothing_on_it_is_an_empty_page_so_page_n_is_slide_n(tmp_path):
    source = _deck(tmp_path / "raw" / "raw_corpus" / "tema.pptx", {3: "solo la nota"}, slides=3)
    document = _document(slides=3)
    # Slide 2 declares a page and no item at all.
    document = docling.DoclingDocument(name="t")
    for number in (1, 2, 3):
        document.add_page(page_no=number, size=docling.Size(width=10, height=10))
        if number != 2:
            document.add_text(
                label=docling.DocItemLabel.PARAGRAPH, text=f"texto {number}", prov=_prov(number)
            )

    read = _pages(source, document=document)

    assert read == ["texto 1\n", "", "texto 3\n\n> **Notas del orador**\n>\n> solo la nota\n"]


def test_a_deck_without_notes_reads_slide_by_slide_exactly_as_docling_writes_it(tmp_path):
    source = _deck(tmp_path / "raw" / "raw_corpus" / "tema.pptx", {})
    document = _document()

    whole = pages.tidy_markdown(pages.export_markdown(document, {}), converted=True)
    assert "\n".join(_pages(source, document=document)) == whole
    assert office.speaker_notes(source) == {}


def test_a_docx_is_still_one_page(tmp_path):
    docx = tmp_path / "cuaderno.docx"
    docx.write_bytes(b"PK")

    read, _ = pages.transcribe_office(docx, _converter(_document()), "m", ES)

    assert len(read) == 1 and "## Diapositiva 3" in read[0]


def test_two_slides_are_never_joined_as_one_sentence(tmp_path):
    # The deterministic seam reads «…sigue» + «y continúa» as a cut sentence and would glue
    # them with a space; a slide is a unit, so the deck's seams settle every boundary.
    slides = ["texto que sigue\n", "y continúa aquí\n"]
    seams = pages.slide_seams(slides)

    assert pages.seam(slides[0], slides[1]) == (pages.SPACE, False)
    assert seams == [{"page": 2, "separator": pages.PARAGRAPH, "drop_head_lines": 0}]
    assert pages.join_pages(slides, seams) == (
        f"texto que sigue\n\n{pages.page_mark(2)}\n\ny continúa aquí"
    )
    assert pages.seams_merged(seams) == 0 and pages.seams_failed(seams) == []


def test_a_deck_not_yet_read_reports_its_slides_as_its_pages(tmp_path):
    source = _deck(tmp_path / "raw" / "raw_corpus" / "tema.pptx", {}, slides=4)
    docx = tmp_path / "cuaderno.docx"
    docx.write_bytes(b"PK")
    broken = tmp_path / "roto.pptx"
    broken.write_bytes(b"PK")

    assert office.slide_count(source) == 4
    assert office.slide_count(docx) == 0 and office.slide_count(broken) == 0


def test_a_note_of_several_paragraphs_and_soft_breaks_is_one_quote(tmp_path):
    source = _deck(
        tmp_path / "raw" / "raw_corpus" / "tema.pptx",
        {1: "primera\x0bsegunda línea  \n\n\n\ntercer párrafo\n"},
    )

    assert office.speaker_notes(source) == {1: "primera\nsegunda línea\n\ntercer párrafo"}
    text = _read(source)
    assert "> primera\n> segunda línea\n>\n> tercer párrafo" in text


def test_the_note_is_the_authors_text_and_the_converter_escape_undo_never_touches_it(tmp_path):
    # `\_` and `&gt;` are what Docling writes and are undone on ITS output; in a note they are
    # what the teacher typed, exactly as in a picture's reading.
    source = _deck(tmp_path / "raw" / "raw_corpus" / "tema.pptx", {1: r"nota\_textual &gt; 3"})

    text = _read(source)

    assert r"> nota\_textual &gt; 3" in text


def test_the_label_follows_the_workspace_language(tmp_path):
    from variatio import prompts

    source = _deck(tmp_path / "raw" / "raw_corpus" / "tema.pptx", {1: "note"})

    assert f"> **{EN_WORDING.SPEAKER_NOTES_LABEL}**" in _read(source, prompts=prompts.of("en"))
    assert f"> **{ES_WORDING.SPEAKER_NOTES_LABEL}**" in _read(source)


def test_a_docx_has_no_notes_and_a_broken_deck_reads_as_having_none(tmp_path):
    docx = tmp_path / "cuaderno.docx"
    docx.write_bytes(b"PK")
    broken = tmp_path / "roto.pptx"
    broken.write_bytes(b"PK")

    assert office.speaker_notes(docx) == {}
    assert office.speaker_notes(broken) == {}


def test_the_deck_version_is_in_the_fingerprint_of_a_deck_only(tmp_path):
    deck = tmp_path / "tema.pptx"
    deck.write_bytes(b"PK")
    docx = tmp_path / "cuaderno.docx"
    docx.write_bytes(b"PK")

    of_deck = pages.fingerprint_for(deck, "m", 200, False)
    of_docx = pages.fingerprint_for(docx, "m", 200, False)

    assert of_deck["deck"] == pages.DECK_VERSION
    assert "deck" not in of_docx
    # A deck read as one page (layout 1, or none at all) is stale, and the reason is named.
    from variatio.entrypoints import transcribe

    stored = {k: v for k, v in of_deck.items() if k != "deck"}
    assert not pages.same_document(stored, of_deck)
    assert not pages.same_document({**stored, "notes": 1}, of_deck)
    assert transcribe._reasons({**stored, "notes": 1}, of_deck) == ["deck"]


def test_the_notes_count_travels_in_the_meta_and_never_in_the_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(
        pages.inference,
        "generate",
        lambda *a, **k: inference.GenerationResponse(response="", thinking=""),
    )
    source = _deck(tmp_path / "raw" / "raw_corpus" / "tema.pptx", {1: "a", 3: "b"})
    cache = tmp_path / "cache"

    read = pages.document_pages(
        source, ES, converter=_converter(_document()), model="m", cache_dir=cache
    )

    meta = pages.read_meta(pages.document_cache_dir(source, cache))
    assert len(read) == 3 and meta["pages"] == 3
    assert meta["notes_total"] == 2
    assert meta["seams"] == pages.slide_seams(read) and meta["seams_merged"] == 0
    assert "notes_total" not in pages.fingerprint_of(meta)
