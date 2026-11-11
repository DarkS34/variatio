"""Transcribing a document page by page, from the page IMAGE and not from its text.

Docling reads these exercise PDFs as text and loses three things at once: it detaches a code
block from the question that cites it, it collapses the block's line breaks, and it drops
the colour that marks the correct option. All three are visible on a rendered page, so the
image is the honest source for this material.

The unit of work and of caching is the PAGE: a real boundary in the document, one model call
per bounded piece of work, and something small enough for a person to review and fix by hand.

An Office document (`.docx`, `.pptx`) declares its structure and Docling translates it, so
it has no page to render; its PICTURES are the part Docling cannot read, and they take the
same route one at a time — each is one model call under `IMAGE_RULES`, keyed by its own
content hash so the logo repeated on every document is read once for the whole workspace.

The package, by what each module does:

    document.py      reading a whole document: cache, re-read, transcribe what is missing
    cache.py         pages, `_meta.json`, fingerprints and the reuse of a donor's pages
    render.py        PDFium: counting, drawing and encoding pages, under `_PDFIUM_LOCK`
    transcribe.py    one page asked of the vision model, its retry and its salvage
    office_pages.py  Office files: slides, speaker notes and body pictures
    images.py        the per-picture transcription cache
    seams.py         joining pages and reviewing the seams between them

Every name is re-exported here, so no importer changed with the split. A test that patches a
name patches the module that looks it up (`document` calls `page_images`, `page_count` and
`_transcribe_page`; `render` holds `_PDFIUM_LOCK`).
"""

from .cache import (
    CONVERTER_CLEANUP_VERSION,
    DECK_VERSION,
    FAILED_PAGE_PREFIXES,
    META_EXTRA,
    META_NAME,
    PAGE_FILE_RE,
    PARTIAL_NAME,
    RENDER_BEFORE,
    RETIRED_FIELDS,
    adopt_pages,
    document_cache_dir,
    failed_pages,
    fingerprint_for,
    fingerprint_of,
    looped_pages,
    read_meta,
    read_pages,
    read_partial,
    reuse_key,
    same_document,
    sampling_record,
    save_partial_page,
    write_pages,
)
from .document import (
    document_markdown,
    document_pages,
    retryable_pages,
    transcribe_pdf,
)
from .images import (
    IMAGES_DIR_NAME,
)
from .office_pages import (
    slide_seams,
    transcribe_office,
)
from .render import (
    A4_AREA_PT,
    encode_page,
    page_count,
    page_images,
    page_picture,
    page_sizes,
    page_texts,
    render_scale,
)
from .seams import (
    MAX_SEAM_DROP_LINES,
    NEWLINE,
    PARAGRAPH,
    SEAM_SCHEMA,
    SEPARATORS,
    SPACE,
    fence_is_open,
    join_pages,
    page_starts,
    review_seams,
    seam,
    seams_failed,
    seams_merged,
    valid_seams,
)
from .transcribe import (
    MD_FENCE_RE,
)

__all__ = [
    "A4_AREA_PT",
    "CONVERTER_CLEANUP_VERSION",
    "DECK_VERSION",
    "FAILED_PAGE_PREFIXES",
    "IMAGES_DIR_NAME",
    "MAX_SEAM_DROP_LINES",
    "MD_FENCE_RE",
    "META_EXTRA",
    "META_NAME",
    "NEWLINE",
    "PAGE_FILE_RE",
    "PARAGRAPH",
    "PARTIAL_NAME",
    "RENDER_BEFORE",
    "RETIRED_FIELDS",
    "SEAM_SCHEMA",
    "SEPARATORS",
    "SPACE",
    "adopt_pages",
    "document_cache_dir",
    "document_markdown",
    "document_pages",
    "encode_page",
    "failed_pages",
    "fence_is_open",
    "fingerprint_for",
    "fingerprint_of",
    "join_pages",
    "looped_pages",
    "page_count",
    "page_images",
    "page_picture",
    "page_sizes",
    "page_starts",
    "page_texts",
    "read_meta",
    "read_pages",
    "read_partial",
    "render_scale",
    "retryable_pages",
    "reuse_key",
    "review_seams",
    "same_document",
    "sampling_record",
    "save_partial_page",
    "seam",
    "seams_failed",
    "seams_merged",
    "slide_seams",
    "transcribe_office",
    "transcribe_pdf",
    "valid_seams",
    "write_pages",
]
