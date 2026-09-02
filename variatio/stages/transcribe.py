"""Phase 0.5 — the raw slots as reviewable markdown pages, ahead of any build.

Transcribing is an ACCELERATOR, never a gate: every builder still runs its own conversion
phase, which hits this same cache when the pages are there and transcribes when they are
not. Nothing here creates anything under `raw/` — that directory is the user's.
"""

from pathlib import Path

from loguru import logger

from .. import config
from .. import prompts as prompts_pkg
from ..builders import _source_docs
from ..core import progress
from ..core.workspace import Workspace
from ..instance import locale

CORPUS = "corpus"
EXEMPLARS = "exemplars"
SLOTS = (CORPUS, EXEMPLARS)

DONE = "done"
PENDING = "pending"
STALE = "stale"

TRANSCRIBE_PHASES = (("transcribe", "Transcribiendo los documentos", 100),)

# What each fingerprint field means in the sentence the screen shows: expiry has to be
# VISIBLE, or a build quietly re-transcribes a whole corpus because somebody nudged the DPI.
# They are CODES and not sentences — the reader's interface has a language of its own — and
# two fields answer to `document` on purpose, since nobody is told which half moved.
_REASONS = {
    "source_sha256": "document",
    "source_bytes": "document",
    "mode": "route",
    "model": "model",
    "dpi": "dpi",
    "ocr": "ocr",
    "prompt_version": "prompt",
    "temperature": "temperature",
    "cleanup": "cleanup",
    "rasteriser": "rasteriser",
}

_UNKNOWN_REASON = "config"


def slot_dir(ws: Workspace, slot: str) -> Path:
    """Return the `raw/` directory one slot reads from."""
    if slot == CORPUS:
        return ws.raw_corpus_dir
    if slot == EXEMPLARS:
        return ws.raw_exemplars_dir
    raise ValueError(f"Unknown slot '{slot}'; expected one of {list(SLOTS)}")


def _slot_ocr(slot: str) -> bool:
    """Return whether this slot's documents are read with OCR."""
    return config.EXEMPLARS_OCR if slot == EXEMPLARS else False


def _slot_converter(slot: str):
    """Return the slot's lazily-opened Docling converter, still unbuilt."""
    if slot == EXEMPLARS:
        return _source_docs.LazyConverter(ocr=config.EXEMPLARS_OCR)
    return _source_docs.LazyConverter(table_structure=False)


def _sources(ws: Workspace, slot: str) -> list[Path]:
    """List the supported documents a slot holds, or nothing when it has no directory."""
    root = slot_dir(ws, slot)
    if not root.is_dir():
        return []
    return _source_docs.list_source_files(root)


def _source_for(ws: Workspace, slot: str, name: str) -> Path:
    """Resolve a document name against the files the slot actually holds.

    A name arriving in a request is checked, never sanitised and used; the library checks
    again further in.
    """
    for source in _sources(ws, slot):
        if source.name == name:
            return source
    raise ValueError(f"No document named '{name}' in slot '{slot}'")


def _cache_dir_for(ws: Workspace, source: Path) -> Path:
    """Return where one document's transcribed pages live."""
    return _source_docs.document_cache_dir(source, ws.markdown_cache_dir)


def _expected_fingerprint(source: Path, slot: str) -> dict:
    """Return the fingerprint this document would be transcribed under right now."""
    return _source_docs.fingerprint_for(
        source, config.TRANSCRIBE_MODEL, config.TRANSCRIBE_DPI, _slot_ocr(slot)
    )


def _reasons(stored: dict, expected: dict) -> list[str]:
    """Name what changed, deduped and in fingerprint order; `config` when nothing is named."""
    changed = [
        key
        for key in expected
        if key in _REASONS and stored.get(key) != expected[key]
    ]
    said: list[str] = []
    for key in changed:
        code = _REASONS[key]
        if code not in said:
            said.append(code)
    return said or [_UNKNOWN_REASON]


def _document_status(source: Path, ws: Workspace, slot: str) -> dict:
    """Report one document as `done` / `pending` / `stale`, and why it is stale."""
    cache_dir = _cache_dir_for(ws, source)
    meta = _source_docs.read_meta(cache_dir)
    pages = _source_docs.read_pages(cache_dir) if meta else []
    expected = _expected_fingerprint(source, slot)

    if not pages:
        return {
            "name": source.name,
            "pages": _source_docs.page_count(source) if source.suffix.lower() == ".pdf" else 0,
            "state": PENDING,
            "reasons": [],
            "chars": 0,
            "seams_merged": 0,
            "failed_pages": 0,
            "images": 0,
            "images_unreadable": 0,
        }

    stored = _source_docs.fingerprint_of(meta)
    current = _source_docs.same_document(stored, expected)
    return {
        "name": source.name,
        "pages": len(pages),
        "state": DONE if current else STALE,
        "reasons": [] if current else _reasons(stored, expected),
        "chars": sum(len(page) for page in pages),
        "seams_merged": _merged(meta),
        "failed_pages": len(meta.get("failed_pages") or []),
        "images": _count(meta, "images_total"),
        "images_unreadable": _count(meta, "images_unreadable"),
    }


def _count(meta: dict, key: str) -> int:
    """Read one of the tallies `_meta.json` carries, `0` for a meta written before it."""
    value = meta.get(key)
    return value if isinstance(value, int) and value > 0 else 0


def _merged(meta: dict) -> int:
    """Return how many page seams the model decided to join."""
    return _source_docs.seams_merged(meta.get("seams"))


def transcription_status(ws: Workspace, slot: str) -> dict:
    """Report a whole slot: every document's state, and the three tallies over them."""
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
    """Transcribe every document of one slot, page by page, and report what came out.

    Pages are written per document, so a cancelled run keeps what it produced and a
    relaunch carries on. One unreadable document is logged and skipped, never fatal.
    """
    sources = _sources(ws, slot)
    summary = {
        "slot": slot,
        "documents": 0,
        "pages": 0,
        "seams_merged": 0,
        "failed_pages": 0,
        "images": 0,
        "images_unreadable": 0,
    }
    if not sources:
        logger.warning(f"No supported document in {slot_dir(ws, slot)}")
        return summary

    converter = _slot_converter(slot)
    ocr = _slot_ocr(slot)
    logger.info(f"Transcribing {len(sources)} document(s) of «{slot}»")

    with progress.overall(TRANSCRIBE_PHASES):
        progress.phase("transcribe", f"0/{len(sources)} documento(s)")
        # NOT «transcribe»: `pages.py` already spends that id on the per-page loop nested
        # inside this one, and the client patches the LAST step carrying an id — so the two
        # loops overwrote each other's counter and neither could be drawn.
        with progress.step(
            "transcribe_documents", "Transcribiendo los documentos", len(sources)
        ) as reporter:
            for idx, source in enumerate(sources, 1):
                progress.checkpoint()
                reporter.start(idx, detail=source.name)
                progress.advance(
                    (idx - 1) / len(sources), f"{source.name} ({idx}/{len(sources)})"
                )
                try:
                    pages = _source_docs.document_pages(
                        source,
                        prompts_pkg.of(locale.prompt_language(ws)),
                        converter=converter,
                        ocr=ocr,
                        tag=f"[{idx}/{len(sources)}] ",
                        cache_dir=ws.markdown_cache_dir,
                    )
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.exception(f"[{source.name}] transcription skipped: {e}")
                    continue
                meta = _source_docs.read_meta(_cache_dir_for(ws, source))
                summary["documents"] += 1
                summary["pages"] += len(pages)
                summary["seams_merged"] += _merged(meta)
                summary["failed_pages"] += len(meta.get("failed_pages") or [])
                summary["images"] += _count(meta, "images_total")
                summary["images_unreadable"] += _count(meta, "images_unreadable")
                progress.emit(
                    "artifact.progress", name=f"transcribe_{slot}", count=summary["pages"]
                )
        progress.advance(1.0, f"{summary['pages']} página(s)")

    logger.success(
        f"Transcription of «{slot}»: {summary['documents']} document(s), "
        f"{summary['pages']} page(s), {summary['seams_merged']} seam(s) joined, "
        f"{summary['images']} picture(s) of which {summary['images_unreadable']} unreadable"
    )
    return summary


# HAND EDITING ------------------------------------------------------------------------------------
#
# A page a human corrected is the whole point of writing the pages out, so none of these
# touches the fingerprint: editing must never make the document look re-transcribable. What
# they do drop are the SEAM records around the page they moved, which were decided against
# text that is no longer there.


def document_pages_listing(ws: Workspace, slot: str, name: str) -> list[dict]:
    """List one document's pages, numbered from 1, flagging the ones the model failed on."""
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
    """Replace one page with a hand-corrected version."""
    cache_dir, meta, pages = _open(ws, slot, name)
    _check_index(index, len(pages))
    pages[index - 1] = text
    # A seam record is named after the page that STARTS at it, so the two around page N are
    # N (what precedes it) and N+1 (what follows it).
    _save(cache_dir, meta, pages, dropped={index, index + 1})


def insert_document_page(
    ws: Workspace, slot: str, name: str, after: int, text: str
) -> int:
    """Insert a page after `after` (0 for the front) and return its new number."""
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
    """Delete one page, refusing to remove the last one.

    A document with zero pages reads as `pending`, and the next build would throw away
    every hand correction without a word.
    """
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
    """Resolve a document and read back its cache directory, metadata and pages."""
    source = _source_for(ws, slot, name)
    cache_dir = _cache_dir_for(ws, source)
    pages = _source_docs.read_pages(cache_dir)
    if not pages:
        raise ValueError(f"'{name}' has no transcribed pages to edit")
    return cache_dir, _source_docs.read_meta(cache_dir), pages


def _check_index(index: int, count: int) -> None:
    """Raise unless `index` names an existing page, counting from 1."""
    if index < 1 or index > count:
        raise ValueError(f"No page {index}; the document has {count}")


def _save(cache_dir: Path, meta: dict, pages: list[str], dropped: set[int]) -> None:
    """Write the pages back under the SAME fingerprint, dropping the named seam records."""
    seams = [
        record
        for record in _source_docs.valid_seams(meta.get("seams"))
        if record["page"] not in dropped
    ]
    _source_docs.write_pages(cache_dir, pages, _source_docs.fingerprint_of(meta), seams)
