"""What a document's transcription keeps on disk: the pages, `_meta.json` and the fingerprint
that decides whether they are still current.
"""

import hashlib
import json
import re
from pathlib import Path

from ... import config
from ... import wording as wording_sets
from ...core import inference, languages, repetition
from ...core.json_io import write_json
from .. import office
from ..files import source_hash
from .seams import seams_failed, seams_merged, valid_seams

PAGE_FILE_RE = re.compile(r"^(\d{3})\.md$")


META_NAME = "_meta.json"


# Written after every page and removed when `_meta.json` lands: a directory holding one and
# not the other is an interrupted transcription, and nothing reads it as a finished document
# because `read_pages` asks for the meta.
PARTIAL_NAME = "_partial.json"


# Fingerprint fields older metas carry that no longer decide anything. `prompt_version`
# expired every page of every subject whenever a prompt changed, and a prompt change is a
# better prompt (retired 2026-09-16): a page read under an older one stays current until
# its document changes or somebody reads it again. Dropped on READ, so no cache is expired
# by the retirement itself.
RETIRED_FIELDS = ("prompt_version",)


# The render fields' values before they were settings, and so what every page read before
# they entered the fingerprint was produced with (2026-10-02).
RENDER_BEFORE = {
    "render_max_a4": 2,
    "png_max_bytes": 2 * 1024 * 1024,
    "jpeg_quality": 90,
    "picture_min_side": 1024,
    "picture_max_pixels": 7_750_000,
    "raster_scale": 4,
}


# What `_meta.json` holds beside the fingerprint, and therefore what is NOT compared when
# deciding whether the cached pages are still current.
META_EXTRA = (
    "pages",
    "seams",
    "seams_merged",
    "seams_failed",
    "failed_pages",
    "images_total",
    "images_unreadable",
    "notes_total",
    "restructured",
)


# The marker a failed page carries, in EVERY language the installation writes: what is
# written goes in the workspace's own words, but `failed_pages` counts pages already on
# disk and cannot ask which language wrote them.
FAILED_PAGE_PREFIXES = tuple(wording_sets.of(code).FAILED_PAGE_PREFIX for code in languages.LANGUAGES)


# The version of `markdown.undo_converter_escapes`, the cleanup applied to Docling's output
# and to nothing else. It is written into the DOCLING fingerprint ONLY: bumping it expires
# the pages that cleanup produced, which is seconds of Docling, while a key in the vlm
# fingerprint would re-transcribe every PDF ever read for a change that never touched them.
CONVERTER_CLEANUP_VERSION = 1


# The version of how a deck is laid out as pages: 1 was one page with the speaker notes
# under their slides, 2 is one page PER SLIDE. Written into the fingerprint of a `.pptx`
# ONLY — a `.docx` has neither slides nor notes and must not be re-read for them — and a
# deck re-read costs seconds of Docling, its pictures being cached by content.
DECK_VERSION = 2


def document_cache_dir(source: str | Path, cache_dir: str | Path) -> Path:
    """Where the pages of one source document are cached."""
    source = Path(source)
    return Path(cache_dir) / source.parent.name / source.name


def _page_path(cache_dir: Path, index: int) -> Path:
    """The file holding page `index`, numbered from one."""
    return cache_dir / f"{index:03d}.md"


def fingerprint_for(source: Path, model: str, dpi: int, ocr: bool) -> dict:
    """The fingerprint of a document, on the route its extension takes it through."""
    is_pdf = source.suffix.lower() == ".pdf"
    return _page_fingerprint(
        source,
        mode="vlm" if is_pdf else "docling",
        model=model,
        dpi=dpi if is_pdf else 0,
        ocr=False if is_pdf else ocr,
    )


def _page_fingerprint(source: Path, mode: str, model: str, dpi: int, ocr: bool) -> dict:
    """Everything that decides what the pages CONTAIN, so that changing any of it expires them.

    The document is identified by its bytes and not by its mtime: a copied or restored
    workspace moves every timestamp and would throw away a whole corpus of transcriptions.
    `TRANSCRIBE_SEAM_CHARS` is deliberately absent — how much of a seam the model is shown
    does not change a single page, and the seam decisions live in `_meta.json` beside them.
    So is the prompt (`RETIRED_FIELDS`): a change to it never re-reads a corpus. The model
    and the sampling are recorded on BOTH routes: on the Docling one they are what the
    pictures were read with, and a page carries those readings inline.
    """
    stat = source.stat()
    fingerprint = {
        "source": source.name,
        "source_sha256": source_hash(source),
        "source_bytes": stat.st_size,
        "mode": mode,
        "model": model,
        "dpi": dpi,
        "ocr": ocr,
        **sampling_record("transcribe" if mode == "vlm" else "transcribe_image"),
        **_render_record(mode),
    }
    if mode == "docling":
        fingerprint["cleanup"] = CONVERTER_CLEANUP_VERSION
        # Whether the metafiles could be rendered: installing LibreOffice has to expire
        # every Office document read without it, or its equations stay unreadable for ever.
        fingerprint["rasteriser"] = Path(office.rasteriser()).name if office.rasteriser() else ""
    if source.suffix.lower() == ".pptx":
        fingerprint["deck"] = DECK_VERSION
    return fingerprint


def _render_record(mode: str) -> dict:
    """What shapes the picture a route sends the model, beyond the DPI: a page's render, or a
    document's pictures and their metafiles."""
    encoding = {
        "png_max_bytes": config.TRANSCRIBE_PAGE_PNG_MAX_BYTES,
        "jpeg_quality": config.TRANSCRIBE_PAGE_JPEG_QUALITY,
    }
    if mode == "vlm":
        return {"render_max_a4": config.TRANSCRIBE_PAGE_MAX_A4_AREAS, **encoding}
    return {
        "picture_min_side": config.TRANSCRIBE_IMAGE_MIN_LONG_SIDE,
        "picture_max_pixels": config.TRANSCRIBE_IMAGE_MAX_PIXELS,
        "raster_scale": config.TRANSCRIBE_METAFILE_RASTER_SCALE,
        **encoding,
    }


def sampling_record(phase: str) -> dict:
    """The sampling a reading was made under, as a fingerprint or an image record keeps it.

    The temperature always; top-k and top-p only when set, so a cache written before they
    could be set stays current for as long as they are left empty.
    """
    sampling = inference.sampling(phase)
    record: dict = {"temperature": sampling.temperature}
    if sampling.top_k is not None:
        record["top_k"] = sampling.top_k
    if sampling.top_p is not None:
        record["top_p"] = sampling.top_p
    return record


def same_document(stored: dict, fingerprint: dict) -> bool:
    """Say whether cached pages were produced for this exact document and settings.

    Pages written before the fingerprint stopped believing timestamps are adopted rather
    than re-transcribed: everything else about them still matches, and the mtime they
    recorded is exactly the field that cannot be trusted.
    """
    if stored == fingerprint:
        return True
    if "source_sha256" in stored or "source_mtime" not in stored:
        return False
    adopted = {k: v for k, v in stored.items() if k != "source_mtime"}
    return {**adopted, "source_sha256": fingerprint["source_sha256"]} == fingerprint


# What a fingerprint says about the document's LOCATION rather than about its content. Two
# copies of one file under two names, in two slots or in two workspaces, differ here and
# nowhere else, so this is exactly what `reuse_key` drops.
_PLACEMENT_FIELDS = ("source",)


def reuse_key(fingerprint: dict) -> tuple:
    """What identifies a transcription that another document could adopt whole.

    The fingerprint minus the file's NAME: everything left is either the bytes
    (`source_sha256`, `source_bytes`) or the settings the pages were produced under, so two
    documents agreeing on this key would be transcribed into the same pages, one model call
    at a time, for nothing. The name is dropped and not compared because it is the one field
    that says where a copy sits rather than what it holds.
    """
    return tuple(
        sorted(
            (key, _hashable(value))
            for key, value in fingerprint.items()
            if key not in _PLACEMENT_FIELDS
        )
    )


def _hashable(value):
    """Make one fingerprint value usable inside a key; every one of them is already flat."""
    return tuple(sorted(value.items())) if isinstance(value, dict) else value


def adopt_pages(donor_dir: str | Path, cache_dir: str | Path, fingerprint: dict) -> int:
    """Copy a finished transcription onto another document, under its own fingerprint.

    Returns how many pages were written, or 0 when the donor turns out not to hold a
    finished document after all — the caller checked its `_meta.json`, but the pages are
    read back from disk here and the two are separate files.

    The pages are COPIED and not linked: a hand correction on either side must not rewrite
    the other, and a workspace that is later deleted must not take somebody else's
    transcription with it. Only the name in the fingerprint differs from the donor's, so
    what lands is what the model would have written.
    """
    pages = read_pages(donor_dir)
    if not pages:
        return 0
    meta = read_meta(donor_dir)
    write_pages(
        cache_dir,
        pages,
        fingerprint,
        valid_seams(meta.get("seams")),
        {
            "images_total": meta.get("images_total", 0),
            "images_unreadable": meta.get("images_unreadable", 0),
        },
        # The same bytes, so a donor's hand-moved pages are this copy's hand-moved pages too.
        restructured=bool(meta.get("restructured")),
    )
    return len(pages)


def read_pages(cache_dir: str | Path) -> list[str]:
    """The cached pages of a finished document, or `[]` when any of them is missing."""
    cache_dir = Path(cache_dir)
    count = read_meta(cache_dir).get("pages")
    if not isinstance(count, int) or count < 1:
        return []
    paths = [_page_path(cache_dir, i) for i in range(1, count + 1)]
    if not all(path.exists() for path in paths):
        return []
    return [path.read_text(encoding="utf-8") for path in paths]


def read_meta(cache_dir: str | Path) -> dict:
    """Read `_meta.json`, answering `{}` for anything unreadable."""
    meta_path = Path(cache_dir) / META_NAME
    if not meta_path.exists():
        return {}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return meta if isinstance(meta, dict) else {}


def write_pages(
    cache_dir: str | Path,
    pages: list[str],
    fingerprint: dict,
    seams: list[dict] | None = None,
    images: dict | None = None,
    restructured: bool = False,
) -> None:
    """Write a finished document's pages and its `_meta.json`, replacing what was there.

    `restructured` records that a person inserted or deleted pages, so the cache's page
    numbers stopped being the file's; `retryable_pages` reads it.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Wipe first: a source that lost pages would otherwise leave the previous run's trailing
    # files behind, and they would be read back as content. The partial marker goes with
    # them — what this function writes is a finished document.
    for stale in cache_dir.iterdir():
        if stale.is_file() and (
            PAGE_FILE_RE.match(stale.name) or stale.name in (META_NAME, PARTIAL_NAME)
        ):
            stale.unlink()
    for index, page in enumerate(pages, 1):
        _page_path(cache_dir, index).write_text(page, encoding="utf-8")
    _write_meta(cache_dir, fingerprint, pages, seams or [], images or {}, restructured)


def _write_meta(
    cache_dir: Path,
    fingerprint: dict,
    pages: list[str],
    seams: list[dict],
    images: dict,
    restructured: bool = False,
) -> None:
    """Write `_meta.json`: the fingerprint plus what the screens read off it."""
    write_json(
        cache_dir / META_NAME,
        {
            **fingerprint,
            "pages": len(pages),
            "seams": [dict(record) for record in seams],
            "seams_merged": seams_merged(seams),
            "seams_failed": seams_failed(seams),
            "failed_pages": failed_pages(pages),
            "images_total": int(images.get("images_total", 0)),
            "images_unreadable": int(images.get("images_unreadable", 0)),
            "notes_total": int(images.get("notes_total", 0)),
            "restructured": bool(restructured),
        },
    )


def failed_pages(pages: list[str]) -> list[int]:
    """The pages that carry the failure marker instead of a transcription."""
    return [
        index
        for index, page in enumerate(pages, 1)
        if page.lstrip().startswith(FAILED_PAGE_PREFIXES)
    ]


def looped_pages(pages: list[str]) -> list[int]:
    """The pages whose cached text ends in a repetition the model stopped on its own.

    The output cap catches a loop that runs; this catches one that stopped — 271 identical
    grid rows cached as a page with content on the reference installation — so the next
    read tries the page again under the second-attempt rule. A page already carrying the
    failure marker is that marker's business and is not looked at.
    """
    return [
        index
        for index, page in enumerate(pages, 1)
        if not page.lstrip().startswith(FAILED_PAGE_PREFIXES) and _holds_loop(page)
    ]


# The verdicts of `_holds_loop`, by the page's digest and the detector's thresholds. `/raw`
# asks `transcription_status` every four seconds while a job runs and the scan is a
# millisecond a page (measured: 1.77 s over the 1 794 cached pages of the reference
# installation), so a slot of several hundred pages would pay a good part of a second per
# poll for an answer that only changes when the page or a threshold does. Bounded, oldest
# out first.
_LOOP_VERDICTS: dict[tuple, bool] = {}


_LOOP_VERDICTS_MAX = 8192


def _holds_loop(page: str) -> bool:
    """Whether a cached page holds a repetition loop, remembered by the page's digest."""
    key = (hashlib.sha1(page.encode("utf-8")).hexdigest(), repetition.signature())
    verdict = _LOOP_VERDICTS.get(key)
    if verdict is None:
        verdict = repetition.detect(page) is not None
        if len(_LOOP_VERDICTS) >= _LOOP_VERDICTS_MAX:
            del _LOOP_VERDICTS[next(iter(_LOOP_VERDICTS))]
        _LOOP_VERDICTS[key] = verdict
    return verdict


def fingerprint_of(meta: dict) -> dict:
    """The fingerprint half of a `_meta.json`, without the counts and the retired fields.

    A meta written before the render fields were recorded was read with the values those
    had then (`RENDER_BEFORE`), and reads as such: recording them expired nothing.
    """
    fingerprint = {
        k: v for k, v in meta.items() if k not in META_EXTRA and k not in RETIRED_FIELDS
    }
    if "mode" in fingerprint:
        for key in _render_record(fingerprint["mode"]):
            fingerprint.setdefault(key, RENDER_BEFORE[key])
    return fingerprint


def read_partial(cache_dir: str | Path | None, fingerprint: dict) -> list[str]:
    """The pages an interrupted run of this same document already paid for."""
    if cache_dir is None:
        return []
    cache_dir = Path(cache_dir)
    path = _partial_path(cache_dir)
    if not path.exists():
        return []
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(marker, dict):
        return []
    stored = marker.get("fingerprint")
    done = marker.get("pages_done")
    if not isinstance(stored, dict) or not same_document(stored, fingerprint):
        return []
    if not isinstance(done, int) or done < 1:
        return []
    pages: list[str] = []
    for index in range(1, done + 1):
        page_path = _page_path(cache_dir, index)
        if not page_path.exists():
            break
        pages.append(page_path.read_text(encoding="utf-8"))
    return pages


def save_partial_page(
    cache_dir: str | Path | None, index: int, page: str, fingerprint: dict
) -> None:
    """Write one page and move the partial marker onto it."""
    if cache_dir is None:
        return
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    _page_path(cache_dir, index).write_text(page, encoding="utf-8")
    write_json(_partial_path(cache_dir), {"fingerprint": fingerprint, "pages_done": index})


def _partial_path(cache_dir: Path) -> Path:
    """The marker recording how far an unfinished transcription got."""
    return cache_dir / PARTIAL_NAME
