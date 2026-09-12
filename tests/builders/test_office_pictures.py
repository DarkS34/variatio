"""The pictures of a Word or PowerPoint document: read one by one, cached by content.

Docling translates the Office formats faithfully and writes `<!-- image -->` for every
picture, which on the reference exemplars was a formula, another formula and the expected
output of a "write a program that prints this" exercise — the part of each document the
extractor most needed and the part it never saw. Each picture is now one model call under
`IMAGE_RULES`, put back where the picture stood. What is pinned here is the splice, the
cache and the marks; what the model answers is the prompt's business and is measured
elsewhere.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from variatio import config
from variatio.builders.source_docs import markdown, pages
from variatio.core import inference
from variatio.prompts.marks import EMPTY_IMAGE_MARK

from ..conftest import ES
from variatio.wording import es as ES_WORDING

docling = pytest.importorskip("docling_core.types.doc")


def _picture(colour: str):
    from PIL import Image

    return docling.ImageRef.from_pil(Image.new("RGB", (20, 10), colour), dpi=72)


def _document():
    """A body with two identical pictures, one Docling could not open, and a header logo."""
    doc = docling.DoclingDocument(name="t")
    doc.add_text(label=docling.DocItemLabel.PARAGRAPH, text="antes")
    doc.add_picture(image=_picture("red"))
    doc.add_text(label=docling.DocItemLabel.PARAGRAPH, text="entre")
    doc.add_picture(image=_picture("red"))
    doc.add_picture()
    doc.add_text(label=docling.DocItemLabel.PARAGRAPH, text="después")
    doc.add_picture(image=_picture("blue"), content_layer=docling.ContentLayer.FURNITURE)
    return doc


def _converter(document):
    return SimpleNamespace(convert=lambda path: SimpleNamespace(document=document))


class _Model:
    """A stand-in for the engine that answers what it is told and counts the calls."""

    def __init__(self, answer: str = "$x$", failing: bool = False):
        self.answer = answer
        self.failing = failing
        self.calls = 0

    def generate(self, model, prompt, **kwargs):
        self.calls += 1
        if self.failing:
            raise inference.InferenceError("sin motor")
        return inference.GenerationResponse(response=self.answer, thinking="")


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "raw" / "raw_exemplars_bank" / "cuaderno.docx"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"PK")
    return path


@pytest.fixture
def model(monkeypatch) -> _Model:
    stub = _Model()
    monkeypatch.setattr(pages.inference, "generate", stub.generate)
    return stub


def _read(source, model_name="m", images_dir=None, document=None):
    """The one page a `.docx` reads as, with its tally."""
    read, tally = pages.transcribe_office(
        source, _converter(document or _document()), model_name, ES, images_dir=images_dir
    )
    assert len(read) == 1
    return read[0], tally


def _blocks(text: str) -> list[str]:
    """The page as its paragraphs; `tidy_markdown` closes a page with one newline."""
    return text.rstrip("\n").split("\n\n")


def test_a_picture_is_read_where_it_stood_and_a_repeated_one_only_once(source, model, tmp_path):
    text, tally = _read(source, images_dir=tmp_path / "images")

    assert _blocks(text) == ["antes", "$x$", "entre", "$x$", ES_WORDING.UNREADABLE_IMAGE_MARK, "después"]
    assert tally == {"images_total": 3, "images_unreadable": 1, "notes_total": 0}
    # Two pictures with the same bytes are one call, and the header logo is furniture the
    # markdown never carries, so it is not read at all.
    assert model.calls == 1
    assert "<!-- image" not in text


def test_a_reading_is_cached_by_content_and_by_what_read_it(source, model, tmp_path, monkeypatch):
    images_dir = tmp_path / "images"
    _read(source, images_dir=images_dir)
    assert model.calls == 1
    assert len(list(images_dir.glob("*.json"))) == 1

    _read(source, images_dir=images_dir)
    assert model.calls == 1, "the same picture under the same model is never read twice"

    _read(source, model_name="otro", images_dir=images_dir)
    assert model.calls == 2, "another model is another reading"

    monkeypatch.setattr(config, "TRANSCRIBE_PROMPT_VERSION", config.TRANSCRIBE_PROMPT_VERSION + 1)
    _read(source, images_dir=images_dir)
    assert model.calls == 3, "a new prompt expires the reading, exactly as it expires a page"


def test_a_logo_leaves_nothing_behind_and_is_remembered(source, tmp_path, monkeypatch):
    stub = _Model(answer=f"`{EMPTY_IMAGE_MARK}`.")
    monkeypatch.setattr(pages.inference, "generate", stub.generate)

    text, _ = _read(source, images_dir=tmp_path / "images")
    assert _blocks(text) == ["antes", "entre", ES_WORDING.UNREADABLE_IMAGE_MARK, "después"]
    assert EMPTY_IMAGE_MARK not in text

    _read(source, images_dir=tmp_path / "images")
    assert stub.calls == 1, "«nothing on it» is an answer worth caching too"


def test_a_failed_reading_leaves_the_mark_and_is_not_cached(source, tmp_path, monkeypatch):
    stub = _Model(failing=True)
    monkeypatch.setattr(pages.inference, "generate", stub.generate)
    monkeypatch.setattr(config, "TRANSCRIBE_MAX_RETRIES", 0)

    text, tally = _read(source, images_dir=tmp_path / "images")

    assert text.count(ES_WORDING.UNREADABLE_IMAGE_MARK) == 3
    assert tally == {"images_total": 3, "images_unreadable": 3, "notes_total": 0}
    assert not list((tmp_path / "images").glob("*.json")), "a failure must be retried next time"


def test_the_converter_escape_undo_never_touches_what_the_model_wrote(source, tmp_path, monkeypatch):
    # Docling escapes `_` and `>` in its own text and `tidy_markdown(converted=True)` undoes
    # exactly that; a reading carrying the same sequences is the model's and stays as it is.
    stub = _Model(answer="`a\\_b &gt; c`")
    monkeypatch.setattr(pages.inference, "generate", stub.generate)
    doc = docling.DoclingDocument(name="t")
    doc.add_text(label=docling.DocItemLabel.PARAGRAPH, text="x_y")
    doc.add_picture(image=_picture("red"))

    text, _ = _read(source, images_dir=tmp_path / "images", document=doc)

    assert _blocks(text) == ["x_y", "`a\\_b &gt; c`"]


def test_without_a_cache_directory_a_repeated_picture_is_still_read_once(source, model):
    text, _ = _read(source, images_dir=None)

    assert text.count("$x$") == 2
    assert model.calls == 1


def test_a_stub_document_exports_as_itself():
    stub = SimpleNamespace(export_to_markdown=lambda: "# Apuntes")

    assert markdown.pictures(stub) == []
    assert markdown.export_markdown(stub, {}) == "# Apuntes"


def test_the_office_pages_carry_the_model_and_expire_with_it(source):
    # Pages written before the pictures were read recorded no model — they depended on
    # none — and read as stale now, which is what makes a workspace re-read its Office files
    # once and only once.
    expected = pages.fingerprint_for(source, "m", 200, False)
    assert expected["mode"] == "docling" and expected["model"] == "m" and expected["dpi"] == 0
    assert expected["temperature"] == config.TRANSCRIBE_TEMPERATURE
    assert "rasteriser" in expected

    stored = {**expected, "model": "", "temperature": None}
    assert not pages.same_document(stored, expected)


def test_the_picture_tallies_travel_in_the_meta_and_never_in_the_fingerprint(source, model, tmp_path):
    cache = tmp_path / "cache"
    pages.document_pages(source, ES, converter=_converter(_document()), model="m", cache_dir=cache)

    meta = json.loads((pages.document_cache_dir(source, cache) / pages.META_NAME).read_text())
    assert meta["images_total"] == 3 and meta["images_unreadable"] == 1
    assert "images_total" not in pages.fingerprint_of(meta)
    assert (cache / pages.IMAGES_DIR_NAME).is_dir()


def test_a_small_picture_is_upscaled_on_white_before_the_call():
    from PIL import Image

    tiny = Image.new("RGBA", (188, 30), (0, 0, 0, 0))
    encoded = Image.open(__import__("io").BytesIO(pages._encode_image(tiny)))

    assert encoded.mode == "RGB"
    assert max(encoded.size) >= pages.IMAGE_MIN_LONG_SIDE
    assert encoded.size[0] // 188 == encoded.size[1] // 30, "a whole factor, the same on both axes"
    assert encoded.getpixel((0, 0)) == (255, 255, 255), "transparent ground reads as paper"
