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
from .cache import (
    _LOOP_VERDICTS,
    _LOOP_VERDICTS_MAX,
    _PLACEMENT_FIELDS,
    CONVERTER_CLEANUP_VERSION,
    DECK_VERSION,
    FAILED_PAGE_PREFIXES,
    META_EXTRA,
    META_NAME,
    PAGE_FILE_RE,
    PARTIAL_NAME,
    RENDER_BEFORE,
    RETIRED_FIELDS,
    _hashable,
    _holds_loop,
    _page_fingerprint,
    _page_path,
    _partial_path,
    _render_record,
    _write_meta,
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
    _read_cached_pages,
    _read_document,
    _read_failed_pages_again,
    _transcribe,
    document_markdown,
    document_pages,
    retryable_pages,
    transcribe_pdf,
)
from .images import (
    _SAMPLING_FIELDS,
    IMAGES_DIR_NAME,
    _encode_image,
    _image_record_path,
    _read_image_cache,
    _transcribe_image,
    _write_image_cache,
)
from .office_pages import (
    _office_pages,
    _read_pictures,
    _slide_text,
    _with_notes,
    slide_seams,
    transcribe_office,
)
from .render import (
    _PDFIUM_LOCK,
    A4_AREA_PT,
    _scanned,
    encode_page,
    page_count,
    page_images,
    page_picture,
    page_sizes,
    page_texts,
    render_scale,
)
from .seams import (
    _BULLET_LINE_RE,
    _CONTINUATION_HEADS,
    _FENCE_LINE_RE,
    _HEADING_LINE_RE,
    _SENTENCE_END_RE,
    _TABLE_DIVIDER_RE,
    _TABLE_ROW_RE,
    MAX_SEAM_DROP_LINES,
    NEWLINE,
    PARAGRAPH,
    SEAM_SCHEMA,
    SEPARATORS,
    SPACE,
    _boundaries,
    _clamp_drop,
    _continues_sentence,
    _drop_lines,
    _drop_reopened_fence,
    _drop_repeated_header,
    _first_line,
    _last_line,
    _parse_seam,
    _review_seam,
    _stitched,
    _trim,
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
    _ask,
    _ask_twice,
    _cause,
    _head,
    _salvaged_page,
    _transcribe_page,
    _unfinished,
    _unwrap_markdown_fence,
)
