"""Phase 0.5 — the raw slots as reviewable markdown pages, ahead of any build.

Transcribing is an ACCELERATOR, never a gate: every builder still runs its own conversion
phase, which hits this same cache when the pages are there and transcribes when they are
not. Nothing here creates anything under `raw/` — that directory is the user's.
"""

from pathlib import Path

from loguru import logger

from .. import config
from .. import prompts as prompts_pkg
from ..builders import source_docs
from ..builders.source_docs.pages import META_NAME
from ..core import paths, progress
from ..core.workspace import Workspace
from ..instance import locale

CORPUS = "corpus"
EXEMPLARS = "exemplars"
SLOTS = (CORPUS, EXEMPLARS)

DONE = "done"
PENDING = "pending"
STALE = "stale"

TRANSCRIBE_PHASES = (("transcribe", "Reading the documents", 100),)

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
    "deck": "deck",
}

_UNKNOWN_REASON = "config"


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


def slot_dir(ws: Workspace, slot: str) -> Path:
    """Return the `raw/` directory one slot reads from."""
    if slot == CORPUS:
        return ws.raw_corpus_dir
    if slot == EXEMPLARS:
        return ws.raw_exemplars_dir
    raise ValueError(f"Unknown slot '{slot}'; expected one of {list(SLOTS)}")


def _sources(ws: Workspace, slot: str) -> list[Path]:
    """List the supported documents a slot holds, or nothing when it has no directory."""
    root = slot_dir(ws, slot)
    if not root.is_dir():
        return []
    return source_docs.list_source_files(root)


def _source_for(ws: Workspace, slot: str, name: str) -> Path:
    """Resolve a document name against the files the slot actually holds.

    A name arriving in a request is checked, never sanitised and used; the library checks
    again further in.
    """
    for source in _sources(ws, slot):
        if source.name == name:
            return source
    raise ValueError(f"No document named '{name}' in slot '{slot}'")


def _document_status(source: Path, ws: Workspace, slot: str) -> dict:
    """Report one document as `done` / `pending` / `stale`, and why it is stale."""
    cache_dir = _cache_dir_for(ws, source)
    meta = source_docs.read_meta(cache_dir)
    pages = source_docs.read_pages(cache_dir) if meta else []
    expected = _expected_fingerprint(source, slot)

    if not pages:
        return {
            "name": source.name,
            "pages": _declared_pages(source),
            "state": PENDING,
            "reasons": [],
            "chars": 0,
            "seams_merged": 0,
            "failed_pages": 0,
            "images": 0,
            "images_unreadable": 0,
        }

    stored = source_docs.fingerprint_of(meta)
    current = source_docs.same_document(stored, expected)
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


def _declared_pages(source: Path) -> int:
    """How many pages a document not yet read will have: a PDF's pages, a deck's slides."""
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        return source_docs.page_count(source)
    if suffix == ".pptx":
        return source_docs.slide_count(source)
    return 0


def _cache_dir_for(ws: Workspace, source: Path) -> Path:
    """Return where one document's transcribed pages live."""
    return source_docs.document_cache_dir(source, ws.markdown_cache_dir)


def _expected_fingerprint(source: Path, slot: str) -> dict:
    """Return the fingerprint this document would be transcribed under right now."""
    return source_docs.fingerprint_for(
        source, config.TRANSCRIBE_MODEL, config.TRANSCRIBE_DPI, _slot_ocr(slot)
    )


def _slot_ocr(slot: str) -> bool:
    """Return whether this slot's documents are read with OCR."""
    return config.EXEMPLARS_OCR if slot == EXEMPLARS else False


def _slot_converter(slot: str):
    """Return the slot's lazily-opened Docling converter, still unbuilt."""
    if slot == EXEMPLARS:
        return source_docs.LazyConverter(ocr=config.EXEMPLARS_OCR)
    return source_docs.LazyConverter(table_structure=False)


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


def _count(meta: dict, key: str) -> int:
    """Read one of the tallies `_meta.json` carries, `0` for a meta written before it."""
    value = meta.get(key)
    return value if isinstance(value, int) and value > 0 else 0


def _merged(meta: dict) -> int:
    """Return how many page seams the model decided to join."""
    return source_docs.seams_merged(meta.get("seams"))


# ADOPTING A TRANSCRIPTION ALREADY IN THE INSTALLATION -----------------------------------------
#
# The same PDF reaches two subjects all the time — a department's exercise sheet, a shared
# set of notes, the same workbook uploaded again after a slug was renamed — and transcribing
# it a second time is one model call per page for an answer that is already on this disk.
# A document is its BYTES here, exactly as `_page_fingerprint` already says, so two copies
# under two names in two workspaces are one document and the pages carry over whole.
#
# It is a shortcut and never a source of truth: nothing is adopted unless every field the
# pages were produced under agrees, and a document nothing matches is simply transcribed.


def adopt_transcriptions(ws: Workspace, slot: str) -> dict:
    """Give every unread document of a slot a transcription the installation already holds.

    Reports `{"adopted": n, "pages": m}`. A document that is already current is left alone;
    a stale one is adopted like a pending one, since what makes it stale is precisely that
    its pages were produced under settings that no longer apply and the donor's were not.

    Best effort by design: it opens no model, and anything it cannot do it does not do —
    the transcription job is still there and still reads the same cache.
    """
    pending = [
        source
        for source in _sources(ws, slot)
        if _document_status(source, ws, slot)["state"] != DONE
    ]
    summary = {"adopted": 0, "pages": 0}
    if not pending:
        return summary

    wanted = {}
    for source in pending:
        try:
            fingerprint = _expected_fingerprint(source, slot)
        except OSError:
            continue
        wanted[source] = fingerprint

    if not wanted:
        return summary
    keys = {source_docs.reuse_key(f) for f in wanted.values()}
    donors: dict[tuple, Path] = {}
    for directory, fingerprint in _transcribed_documents():
        key = source_docs.reuse_key(fingerprint)
        if key in keys and key not in donors:
            donors[key] = directory
    if not donors:
        return summary

    for source, fingerprint in wanted.items():
        cache_dir = _cache_dir_for(ws, source)
        donor = donors.get(source_docs.reuse_key(fingerprint))
        if donor is None or donor == cache_dir:
            continue
        try:
            pages = source_docs.adopt_pages(donor, cache_dir, fingerprint)
        except OSError as exc:
            logger.warning(f"[{source.name}] could not adopt a known transcription: {exc}")
            continue
        if not pages:
            continue
        summary["adopted"] += 1
        summary["pages"] += pages
        logger.info(
            f"[{source.name}] {pages} page(s) taken from '{donor}': "
            "the same document was already transcribed here"
        )
    return summary


def _transcribed_documents() -> list[tuple[Path, dict]]:
    """Every finished transcription of the installation, as `(directory, fingerprint)`.

    One pass over `workspaces/*/cache/markdown/*/*/_meta.json` and no index file beside it:
    the meta is small, the count is one entry per document the installation has ever read,
    and an index would be a second writer of state that could disagree with the pages.
    """
    found: list[tuple[Path, dict]] = []
    for meta_path in sorted(paths.WORKSPACES_DIR.glob("*/cache/markdown/*/*/" + META_NAME)):
        meta = source_docs.read_meta(meta_path.parent)
        if meta:
            found.append((meta_path.parent, source_docs.fingerprint_of(meta)))
    return found


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

    # Before the first model call: whatever this installation has already read is copied in,
    # and the loop below then finds it cached. It costs one pass over the meta files and it
    # is what makes re-uploading a document somebody else already transcribed instantaneous.
    adopted = adopt_transcriptions(ws, slot)
    if adopted["adopted"]:
        logger.success(
            f"{adopted['adopted']} document(s) of «{slot}» reused a transcription already "
            f"in this installation: {adopted['pages']} page(s) with no model call"
        )

    converter = _slot_converter(slot)
    ocr = _slot_ocr(slot)
    logger.info(f"Transcribing {len(sources)} document(s) of «{slot}»")

    with progress.overall(TRANSCRIBE_PHASES):
        progress.phase("transcribe", f"0/{len(sources)} documento(s)")
        # NOT "transcribe": `pages.py` already spends that id on the per-page loop nested
        # inside this one, and the client patches the LAST step carrying an id — so the two
        # loops overwrote each other's counter and neither could be drawn.
        with progress.step(
            "transcribe_documents", "Reading the documents", len(sources)
        ) as reporter:
            for idx, source in enumerate(sources, 1):
                progress.checkpoint()
                reporter.start(idx, detail=source.name)
                progress.advance(
                    (idx - 1) / len(sources), f"{source.name} ({idx}/{len(sources)})"
                )
                try:
                    pages = source_docs.document_pages(
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
                meta = source_docs.read_meta(_cache_dir_for(ws, source))
                summary["documents"] += 1
                summary["pages"] += len(pages)
                summary["seams_merged"] += _merged(meta)
                summary["failed_pages"] += len(meta.get("failed_pages") or [])
                summary["images"] += _count(meta, "images_total")
                summary["images_unreadable"] += _count(meta, "images_unreadable")
                progress.emit(
                    "artifact.progress", name=f"transcribe_{slot}", count=summary["pages"]
                )
        progress.advance(1.0, f"{summary['pages']} page(s)")

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
    pages = source_docs.read_pages(_cache_dir_for(ws, source))
    failed = set(source_docs.failed_pages(pages))
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
    cache_dir, meta, pages = _open_document(ws, slot, name)
    _check_index(index, len(pages))
    pages[index - 1] = text
    # A seam record is named after the page that STARTS at it, so the two around page N are
    # N (what precedes it) and N+1 (what follows it).
    _save_document(cache_dir, meta, pages, dropped={index, index + 1})


def insert_document_page(
    ws: Workspace, slot: str, name: str, after: int, text: str
) -> int:
    """Insert a page after `after` (0 for the front) and return its new number."""
    cache_dir, meta, pages = _open_document(ws, slot, name)
    count = len(pages)
    if after < 0 or after > count:
        raise ValueError(f"Cannot insert after page {after} of {count}")
    pages.insert(after, text)
    # Everything from the insertion point on is renumbered, so every seam record beyond it
    # now names a boundary between different pages.
    _save_document(cache_dir, meta, pages, dropped=set(range(after + 1, count + 2)))
    return after + 1


def delete_document_page(ws: Workspace, slot: str, name: str, index: int) -> None:
    """Delete one page, refusing to remove the last one.

    A document with zero pages reads as `pending`, and the next build would throw away
    every hand correction without a word.
    """
    cache_dir, meta, pages = _open_document(ws, slot, name)
    count = len(pages)
    _check_index(index, count)
    if count == 1:
        raise ValueError(
            "Refusing to delete the only page: the document would read as never "
            "transcribed and the next build would silently redo it."
        )
    del pages[index - 1]
    _save_document(cache_dir, meta, pages, dropped=set(range(index, count + 2)))


def _open_document(ws: Workspace, slot: str, name: str) -> tuple[Path, dict, list[str]]:
    """Resolve a document and read back its cache directory, metadata and pages."""
    source = _source_for(ws, slot, name)
    cache_dir = _cache_dir_for(ws, source)
    pages = source_docs.read_pages(cache_dir)
    if not pages:
        raise ValueError(f"'{name}' has no transcribed pages to edit")
    return cache_dir, source_docs.read_meta(cache_dir), pages


def _check_index(index: int, count: int) -> None:
    """Raise unless `index` names an existing page, counting from 1."""
    if index < 1 or index > count:
        raise ValueError(f"No page {index}; the document has {count}")


def _save_document(cache_dir: Path, meta: dict, pages: list[str], dropped: set[int]) -> None:
    """Write the pages back under the SAME fingerprint, dropping the named seam records."""
    seams = [
        record
        for record in source_docs.valid_seams(meta.get("seams"))
        if record["page"] not in dropped
    ]
    source_docs.write_pages(cache_dir, pages, source_docs.fingerprint_of(meta), seams)
