"""Docling escapes what it writes; the corpus is what the page said, not what Docling wrote.

`docling_core`'s markdown serializer post-processes every text span with exactly two steps —
`re.sub(r"(?<!\\)_", r"\\_")` and `html.escape(text, quote=False)` — so a `.docx` exercise
sheet reaches the exemplars bank saying `float -&gt; str`, `0 &lt;= nota &lt;= 10` and
`nota\\_textual`. Those items are the few-shot block, so the model is taught an arrow and a
comparison operator that no language has.

What must NOT be undone is the other side of the same coin: a `.md` a person wrote, a page
the VLM transcribed (where `\\|`, `\\#` and `\\$` are deliberate LaTeX and table syntax), and
anything inside a Docling code fence — the serializer turns both escapes OFF there, so a
`&gt;` inside one is the document's own.
"""

import json
from pathlib import Path
from types import SimpleNamespace

from variatio.builders._source_docs import markdown, pages


class _Converter:
    def __init__(self, text: str):
        self.text = text
        self.calls = 0

    def convert(self, path: str):
        self.calls += 1
        return SimpleNamespace(document=SimpleNamespace(export_to_markdown=lambda: self.text))


def _docx(tmp_path: Path) -> Path:
    source = tmp_path / "raw" / "raw_exemplars_bank" / "WB3a.docx"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"not really a docx")
    return source


# The exact three lines the reference corpus is damaged on.
def test_the_converters_escapes_are_undone(tmp_path):
    converter = _Converter(
        "def nota\\_textual(nota):\n\nfloat -&gt; str\n\nPRE: 0 &lt;= nota &lt;=10\n"
    )

    text = markdown.to_markdown(converter, _docx(tmp_path), use_cache=False)

    assert "def nota_textual(nota):" in text
    assert "float -> str" in text
    assert "PRE: 0 <= nota <=10" in text
    assert "&gt;" not in text and "&lt;" not in text and "\\_" not in text


# `html.escape` writes `&` first, so a source `&lt;` leaves as `&amp;lt;`. One left-to-right
# pass inverts that and stops: `re.sub` never rescans what it replaced.
def test_an_escaped_ampersand_survives_as_one_entity():
    assert markdown.undo_converter_escapes("&amp;lt; y &amp;") == "&lt; y &"


def test_the_undo_is_the_exact_inverse_of_what_docling_applies():
    import html
    import re

    original = 'a_b & c < d > e "f" \'g\' h_i'
    escaped = html.escape(re.sub(r"(?<!\\)_", r"\_", original), quote=False)

    assert escaped != original
    assert markdown.undo_converter_escapes(escaped) == original


# The serializer writes code with both escapes off, so anything inside a fence is the
# document's own text. `tidy_markdown` masks fences before it runs, and that is what keeps
# it that way.
def test_a_code_fence_is_left_exactly_as_the_document_had_it(tmp_path):
    fenced = "prosa a\\_b\n\n```python\nif a &lt; b and x\\_y:\n    pass\n```\n"

    text = markdown.to_markdown(_Converter(fenced), _docx(tmp_path), use_cache=False)

    assert "prosa a_b" in text
    assert "if a &lt; b and x\\_y:" in text


# A `.md` is not converter output: `&gt;` there is what somebody typed.
def test_markdown_written_by_a_person_is_not_unescaped(tmp_path):
    source = tmp_path / "raw" / "raw_corpus" / "notas.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("En HTML se escribe &lt;div&gt; y el guión bajo va como \\_\n", encoding="utf-8")

    assert markdown.to_markdown(None, source, use_cache=False) == (
        "En HTML se escribe &lt;div&gt; y el guión bajo va como \\_\n"
    )


# The VLM writes `\|` inside a table cell and `\#` inside LaTeX on purpose; restoring them
# would break the construct. It reaches `tidy_markdown` without the flag, which is the only
# thing keeping them.
def test_a_transcribed_page_keeps_the_escapes_the_model_meant():
    page = "| $A' \\rightarrow \\cdot A\\#$ | `<letra>(<letra>\\|<dígito>)*` |\n"

    assert "\\#" in markdown.tidy_markdown(page)
    assert "\\|" in markdown.tidy_markdown(page)


# Docling is the expensive half and its output does not change, so an improvement to the
# cleanup must not cost a reconversion — the same promise `_refresh` already made.
def test_a_cached_conversion_is_healed_without_calling_docling_again(tmp_path):
    source = _docx(tmp_path)
    cache = tmp_path / "cache" / "markdown"
    cached = markdown.markdown_cache_path(source, cache)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text("float -&gt; str y nota\\_textual\n", encoding="utf-8")
    markdown.markdown_meta_path(cached).write_text(
        json.dumps({"source": source.name, "source_sha256": markdown.source_hash(source)}),
        encoding="utf-8",
    )
    converter = _Converter("no debería llamarse")

    text = markdown.to_markdown(converter, source, cache_dir=cache)

    assert converter.calls == 0
    assert text == "float -> str y nota_textual\n"
    assert cached.read_text(encoding="utf-8") == text


# The pages of a `.docx` are cached too, and they do NOT go through `_refresh`. Expiring
# them is what heals a workspace transcribed before the cleanup existed.
def test_only_the_docling_route_expires_when_the_cleanup_changes(tmp_path):
    docx = _docx(tmp_path)
    pdf = docx.with_name("examen.pdf")
    pdf.write_bytes(b"%PDF-1.4")

    assert pages.fingerprint_for(docx, "m", 200, False)["cleanup"] == (
        pages.CONVERTER_CLEANUP_VERSION
    )
    # Hours of model time: a key added here would re-transcribe every PDF ever read.
    assert "cleanup" not in pages.fingerprint_for(pdf, "m", 200, False)


def test_pages_transcribed_before_the_cleanup_read_as_stale(tmp_path):
    docx = _docx(tmp_path)
    expected = pages.fingerprint_for(docx, "", 0, True)
    stored = {k: v for k, v in expected.items() if k != "cleanup"}

    assert not pages.same_document(stored, expected)
