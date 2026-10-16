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

from ...core import inference, progress
from ..markdown import export_markdown, page_mark, tidy_markdown
from .seams import (
    _boundaries,
    _BULLET_LINE_RE,
    _clamp_drop,
    _CONTINUATION_HEADS,
    _continues_sentence,
    _drop_lines,
    _drop_reopened_fence,
    _drop_repeated_header,
    fence_is_open,
    _FENCE_LINE_RE,
    _first_line,
    _HEADING_LINE_RE,
    join_pages,
    _last_line,
    MAX_SEAM_DROP_LINES,
    NEWLINE,
    page_starts,
    PARAGRAPH,
    _parse_seam,
    _review_seam,
    review_seams,
    seam,
    SEAM_SCHEMA,
    seams_failed,
    seams_merged,
    _SENTENCE_END_RE,
    SEPARATORS,
    SPACE,
    _stitched,
    _TABLE_DIVIDER_RE,
    _TABLE_ROW_RE,
    _trim,
    valid_seams,
)
from .transcribe import (
    _ask,
    _ask_twice,
    _cause,
    _head,
    MD_FENCE_RE,
    _salvaged_page,
    _transcribe_page,
    _unfinished,
    _unwrap_markdown_fence,
)
from .render import (
    A4_AREA_PT,
    encode_page,
    page_count,
    page_images,
    page_picture,
    page_sizes,
    page_texts,
    _PDFIUM_LOCK,
    render_scale,
    _scanned,
)
from .cache import (
    adopt_pages,
    CONVERTER_CLEANUP_VERSION,
    DECK_VERSION,
    document_cache_dir,
    FAILED_PAGE_PREFIXES,
    failed_pages,
    fingerprint_for,
    fingerprint_of,
    _hashable,
    _holds_loop,
    _LOOP_VERDICTS,
    _LOOP_VERDICTS_MAX,
    looped_pages,
    META_EXTRA,
    META_NAME,
    PAGE_FILE_RE,
    _page_fingerprint,
    _page_path,
    PARTIAL_NAME,
    _partial_path,
    _PLACEMENT_FIELDS,
    read_meta,
    read_pages,
    read_partial,
    RENDER_BEFORE,
    _render_record,
    RETIRED_FIELDS,
    reuse_key,
    same_document,
    sampling_record,
    save_partial_page,
    _write_meta,
    write_pages,
)
from .images import (
    _encode_image,
    _image_record_path,
    IMAGES_DIR_NAME,
    _read_image_cache,
    _SAMPLING_FIELDS,
    _transcribe_image,
    _write_image_cache,
)
from .office_pages import (
    _office_pages,
    _read_pictures,
    slide_seams,
    _slide_text,
    transcribe_office,
    _with_notes,
)
from .document import (
    document_markdown,
    document_pages,
    _read_cached_pages,
    _read_document,
    _read_failed_pages_again,
    retryable_pages,
    _transcribe,
    transcribe_pdf,
)
