import json
import os
from pathlib import Path
from types import SimpleNamespace

from variatio.builders._source_docs import markdown, pages

LATER = 2_000_000_000


def _document(tmp_path: Path, name: str, text: str) -> Path:
    source = tmp_path / "raw" / "raw_exemplars_bank" / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(text, encoding="utf-8")
    return source


def _hand_edit(source: Path, cache: Path, text: str) -> None:
    page = pages.document_cache_dir(source, cache) / "001.md"
    page.write_text(text, encoding="utf-8")


def _meta(source: Path, cache: Path) -> dict:
    meta_path = pages.document_cache_dir(source, cache) / pages.META_NAME
    return json.loads(meta_path.read_text(encoding="utf-8"))


class _Converter:
    def __init__(self, text: str):
        self.text = text
        self.calls = 0

    def convert(self, path: str):
        self.calls += 1
        return SimpleNamespace(
            document=SimpleNamespace(export_to_markdown=lambda: self.text)
        )


def test_pages_survive_a_copy_that_only_moves_the_timestamp(tmp_path):
    cache = tmp_path / "cache" / "markdown"
    source = _document(tmp_path, "examen.md", "una pregunta")
    pages.document_pages(source, cache_dir=cache)
    _hand_edit(source, cache, "corregido a mano")

    os.utime(source, (LATER, LATER))

    assert pages.document_pages(source, cache_dir=cache) == ["corregido a mano"]


def test_pages_are_rebuilt_when_the_document_itself_changes(tmp_path):
    cache = tmp_path / "cache" / "markdown"
    source = _document(tmp_path, "examen.md", "una pregunta")
    pages.document_pages(source, cache_dir=cache)
    _hand_edit(source, cache, "corregido a mano")

    source.write_text("otra pregunta", encoding="utf-8")

    assert pages.document_pages(source, cache_dir=cache) == ["otra pregunta\n"]


def test_pages_cached_before_the_hash_are_adopted_and_rewritten(tmp_path):
    cache = tmp_path / "cache" / "markdown"
    source = _document(tmp_path, "examen.md", "una pregunta")
    pages.document_pages(source, cache_dir=cache)

    legacy = {k: v for k, v in _meta(source, cache).items() if k != "source_sha256"}
    legacy["source_mtime"] = 1.0
    (pages.document_cache_dir(source, cache) / pages.META_NAME).write_text(
        json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _hand_edit(source, cache, "corregido a mano")

    assert pages.document_pages(source, cache_dir=cache) == ["corregido a mano"]
    rewritten = _meta(source, cache)
    assert "source_mtime" not in rewritten
    assert rewritten["source_sha256"]


def test_pages_of_a_different_document_of_the_same_size_are_not_adopted(tmp_path):
    cache = tmp_path / "cache" / "markdown"
    source = _document(tmp_path, "examen.md", "una pregunta")
    pages.document_pages(source, cache_dir=cache)
    _hand_edit(source, cache, "corregido a mano")

    source.write_text("una respuesta", encoding="utf-8")

    assert pages.document_pages(source, cache_dir=cache) == ["una respuesta\n"]


def test_markdown_is_not_reconverted_when_only_the_timestamp_moves(tmp_path):
    cache = tmp_path / "cache" / "markdown"
    source = _document(tmp_path, "apuntes.docx", "bytes")
    converter = _Converter("# Apuntes")

    markdown.to_markdown(converter, source, cache_dir=cache)
    os.utime(source, (LATER, LATER))
    markdown.to_markdown(converter, source, cache_dir=cache)

    assert converter.calls == 1


def test_markdown_is_reconverted_when_the_document_changes(tmp_path):
    cache = tmp_path / "cache" / "markdown"
    source = _document(tmp_path, "apuntes.docx", "bytes")
    converter = _Converter("# Apuntes")

    markdown.to_markdown(converter, source, cache_dir=cache)
    source.write_text("otros bytes", encoding="utf-8")
    markdown.to_markdown(converter, source, cache_dir=cache)

    assert converter.calls == 2


def test_markdown_cached_before_the_sidecar_falls_back_to_the_timestamp(tmp_path):
    cache = tmp_path / "cache" / "markdown"
    source = _document(tmp_path, "apuntes.docx", "bytes")
    converter = _Converter("# Apuntes")

    markdown.to_markdown(converter, source, cache_dir=cache)
    cached = markdown.markdown_cache_path(source, cache)
    markdown.markdown_meta_path(cached).unlink()
    os.utime(source, (LATER, LATER))
    markdown.to_markdown(converter, source, cache_dir=cache)

    assert converter.calls == 2
