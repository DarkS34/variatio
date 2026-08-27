"""Phase 0.5 — the raw slots as reviewable markdown pages, ahead of any build.

Transcribing is an ACCELERATOR, never a gate: every builder still runs its own conversion
phase, which hits this same cache when the pages are there and transcribes when they are
not. Nothing here creates anything under `raw/` — that directory is the user's.
"""

from pathlib import Path

from loguru import logger

from .. import config
from ..builders import _source_docs
from ..core import progress
from ..core.workspace import Workspace

CORPUS = "corpus"
EXEMPLARS = "exemplars"
SLOTS = (CORPUS, EXEMPLARS)

DONE = "done"
PENDING = "pending"
STALE = "stale"

TRANSCRIBE_PHASES = (("transcribe", "Transcribiendo los documentos", 100),)

# What each fingerprint field means in the sentence the screen shows. The point of naming
# them is that expiry has to be VISIBLE: a build that quietly re-transcribed a whole corpus
# because somebody nudged the DPI is exactly what this is here to stop.
_REASONS = {
    "source_sha256": "el documento cambió",
    "source_bytes": "el documento cambió",
    "mode": "la ruta de transcripción cambió",
    "model": "el modelo de transcripción cambió",
    "dpi": "la resolución de render cambió",
    "ocr": "el OCR cambió",
    "prompt_version": "el prompt de transcripción cambió",
    "temperature": "la temperatura de transcripción cambió",
}


def slot_dir(ws: Workspace, slot: str) -> Path:
    if slot == CORPUS:
        return ws.raw_corpus_dir
    if slot == EXEMPLARS:
        return ws.raw_exemplars_dir
    raise ValueError(f"Unknown slot '{slot}'; expected one of {list(SLOTS)}")


def _slot_ocr(slot: str) -> bool:
    return config.EXEMPLARS_OCR if slot == EXEMPLARS else False


def _slot_converter(slot: str):
    if slot == EXEMPLARS:
        return _source_docs.LazyConverter(ocr=config.EXEMPLARS_OCR)
    return _source_docs.LazyConverter(table_structure=False)


def _sources(ws: Workspace, slot: str) -> list[Path]:
    root = slot_dir(ws, slot)
    if not root.is_dir():
        return []
    return _source_docs.list_source_files(root)


def _source_for(ws: Workspace, slot: str, name: str) -> Path:
    for source in _sources(ws, slot):
        if source.name == name:
            return source
    raise ValueError(f"No document named '{name}' in slot '{slot}'")


def _cache_dir_for(ws: Workspace, source: Path) -> Path:
    return _source_docs.document_cache_dir(source, ws.markdown_cache_dir)


def _expected_fingerprint(source: Path, slot: str) -> dict:
    return _source_docs.fingerprint_for(
        source, config.TRANSCRIBE_MODEL, config.TRANSCRIBE_DPI, _slot_ocr(slot)
    )


def _reason(stored: dict, expected: dict) -> str:
    changed = [
        key
        for key in expected
        if key in _REASONS and stored.get(key) != expected[key]
    ]
    said: list[str] = []
    for key in changed:
        text = _REASONS[key]
        if text not in said:
            said.append(text)
    return "; ".join(said) or "la configuración de transcripción cambió"


def _document_status(source: Path, ws: Workspace, slot: str) -> dict:
    cache_dir = _cache_dir_for(ws, source)
    meta = _source_docs.read_meta(cache_dir)
    pages = _source_docs.read_pages(cache_dir) if meta else []
    expected = _expected_fingerprint(source, slot)

    if not pages:
        return {
            "name": source.name,
            "pages": _source_docs.page_count(source) if source.suffix.lower() == ".pdf" else 0,
            "state": PENDING,
            "reason": None,
            "chars": 0,
            "seams_merged": 0,
            "failed_pages": 0,
        }

    stored = _source_docs.fingerprint_of(meta)
    current = _source_docs.same_document(stored, expected)
    return {
        "name": source.name,
        "pages": len(pages),
        "state": DONE if current else STALE,
        "reason": None if current else _reason(stored, expected),
        "chars": sum(len(page) for page in pages),
        "seams_merged": _merged(meta),
        "failed_pages": len(meta.get("failed_pages") or []),
    }


def _merged(meta: dict) -> int:
    return _source_docs.seams_merged(meta.get("seams"))


def transcription_status(ws: Workspace, slot: str) -> dict:
    documents = [_document_status(source, ws, slot) for source in _sources(ws, slot)]
    return {
        "slot": slot,
        "documents": documents,
        "done": sum(1 for d in documents if d["state"] == DONE),
        "pending": sum(1 for d in documents if d["state"] == PENDING),
        "stale": sum(1 for d in documents if d["state"] == STALE),
        "total_pages": sum(d["pages"] for d in documents),
    }


def transcribe_slot(ws: Workspace, slot: str) -> dict:
    sources = _sources(ws, slot)
    summary = {
        "slot": slot,
        "documents": 0,
        "pages": 0,
        "seams_merged": 0,
        "failed_pages": 0,
    }
    if not sources:
        logger.warning(f"Ningún documento admitido en {slot_dir(ws, slot)}")
        return summary

    converter = _slot_converter(slot)
    ocr = _slot_ocr(slot)
    logger.info(f"Transcribiendo {len(sources)} documento(s) de «{slot}»")

    with progress.overall(TRANSCRIBE_PHASES):
        progress.phase("transcribe", f"0/{len(sources)} documento(s)")
        with progress.step(
            "transcribe", "Transcribiendo los documentos", len(sources)
        ) as reporter:
            for idx, source in enumerate(sources, 1):
                progress.checkpoint()
                reporter.tick(idx, detail=source.name)
                progress.advance(
                    (idx - 1) / len(sources), f"{source.name} ({idx}/{len(sources)})"
                )
                try:
                    pages = _source_docs.document_pages(
                        source,
                        converter=converter,
                        ocr=ocr,
                        tag=f"[{idx}/{len(sources)}] ",
                        cache_dir=ws.markdown_cache_dir,
                    )
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.exception(f"[{source.name}] transcripción omitida: {e}")
                    continue
                meta = _source_docs.read_meta(_cache_dir_for(ws, source))
                summary["documents"] += 1
                summary["pages"] += len(pages)
                summary["seams_merged"] += _merged(meta)
                summary["failed_pages"] += len(meta.get("failed_pages") or [])
                progress.emit(
                    "artifact.progress", name=f"transcribe_{slot}", count=summary["pages"]
                )
        progress.advance(1.0, f"{summary['pages']} página(s)")

    logger.success(
        f"Transcripción de «{slot}»: {summary['documents']} documento(s), "
        f"{summary['pages']} página(s), {summary['seams_merged']} costura(s) unidas"
    )
    return summary


# HAND EDITING ------------------------------------------------------------------------------------
#
# A page a human corrected is the whole point of writing the pages out, so none of these
# touches the fingerprint: editing must never make the document look re-transcribable. What
# they do drop are the SEAM records around the page they moved, which were decided against
# text that is no longer there — the deterministic rule takes those seams back.


def document_pages_listing(ws: Workspace, slot: str, name: str) -> list[dict]:
    source = _source_for(ws, slot, name)
    pages = _source_docs.read_pages(_cache_dir_for(ws, source))
    failed = set(_source_docs.failed_pages(pages))
    return [
        {
            "index": index,
            "text": page,
            "chars": len(page),
            "failed": index in failed,
        }
        for index, page in enumerate(pages, 1)
    ]


def write_document_page(
    ws: Workspace, slot: str, name: str, index: int, text: str
) -> None:
    cache_dir, meta, pages = _open(ws, slot, name)
    _check_index(index, len(pages))
    pages[index - 1] = text
    # A seam record is named after the page that STARTS at it, so the two around page N are
    # N (what precedes it) and N+1 (what follows it).
    _save(cache_dir, meta, pages, dropped={index, index + 1})


def insert_document_page(
    ws: Workspace, slot: str, name: str, after: int, text: str
) -> int:
    cache_dir, meta, pages = _open(ws, slot, name)
    count = len(pages)
    if after < 0 or after > count:
        raise ValueError(f"Cannot insert after page {after} of {count}")
    pages.insert(after, text)
    # Everything from the insertion point on is renumbered, so every seam record beyond it
    # now names a boundary between different pages.
    _save(cache_dir, meta, pages, dropped=set(range(after + 1, count + 2)))
    return after + 1


def delete_document_page(ws: Workspace, slot: str, name: str, index: int) -> None:
    cache_dir, meta, pages = _open(ws, slot, name)
    count = len(pages)
    _check_index(index, count)
    if count == 1:
        raise ValueError(
            "Refusing to delete the only page: the document would read as never "
            "transcribed and the next build would silently redo it."
        )
    del pages[index - 1]
    _save(cache_dir, meta, pages, dropped=set(range(index, count + 2)))


def _open(ws: Workspace, slot: str, name: str) -> tuple[Path, dict, list[str]]:
    source = _source_for(ws, slot, name)
    cache_dir = _cache_dir_for(ws, source)
    pages = _source_docs.read_pages(cache_dir)
    if not pages:
        raise ValueError(f"'{name}' has no transcribed pages to edit")
    return cache_dir, _source_docs.read_meta(cache_dir), pages


def _check_index(index: int, count: int) -> None:
    if index < 1 or index > count:
        raise ValueError(f"No page {index}; the document has {count}")


def _save(cache_dir: Path, meta: dict, pages: list[str], dropped: set[int]) -> None:
    seams = [
        record
        for record in _source_docs.valid_seams(meta.get("seams"))
        if record["page"] not in dropped
    ]
    _source_docs.write_pages(cache_dir, pages, _source_docs.fingerprint_of(meta), seams)
