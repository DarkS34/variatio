"""Reading a source document: files, markdown, chunking and page transcription.

Shared by all three builders — anything about reading a source file belongs here and is
never duplicated into one of them — and by whatever else reads a raw document: the
transcription (`entrypoints/transcribe.py`), the server (`server/raw_data.py`,
`server/originals.py`, `server/approvals.py`), the tutor's passages and the evaluation's plain
reading. That is why it sits beside `builders/` and not inside it (until 2026-10-16 it was
`builders/source_docs/`).

`pages` (a package, one module per step of a transcription) is the only part that talks to a
model; `markdown` and `chunking` import neither `inference` nor `progress`, which is the
property the split exists to keep checkable; `office` talks to LibreOffice and to no model.
"""

from . import chunking, files, markdown, office, pages
from .chunking import chunk_markdown, chunk_sections, chunk_text
from .files import (
    CONVERTED_EXTS,
    OFFICE_EXTS,
    PLAIN_TEXT_EXTS,
    SUPPORTED_EXTS,
    LazyConverter,
    default_converter,
    list_source_files,
    name_order,
)
from .markdown import (
    headings_by_level,
    markdown_cache_path,
    page_mark,
    split_blocks,
    strip_page_marks,
    tidy_markdown,
    to_markdown,
)
from .office import slide_count
from .pages import (
    FAILED_PAGE_PREFIXES,
    PARAGRAPH,
    adopt_pages,
    document_cache_dir,
    document_markdown,
    document_pages,
    failed_pages,
    fingerprint_for,
    fingerprint_of,
    join_pages,
    page_count,
    page_images,
    page_picture,
    page_sizes,
    page_starts,
    page_texts,
    read_meta,
    read_pages,
    retryable_pages,
    reuse_key,
    review_seams,
    same_document,
    seam,
    seams_failed,
    seams_merged,
    slide_seams,
    transcribe_office,
    transcribe_pdf,
    valid_seams,
    write_pages,
)

__all__ = [
    "CONVERTED_EXTS",
    "OFFICE_EXTS",
    "PARAGRAPH",
    "PLAIN_TEXT_EXTS",
    "SUPPORTED_EXTS",
    "FAILED_PAGE_PREFIXES",
    "LazyConverter",
    "adopt_pages",
    "chunk_markdown",
    "chunk_sections",
    "chunk_text",
    "chunking",
    "default_converter",
    "document_cache_dir",
    "document_markdown",
    "document_pages",
    "failed_pages",
    "files",
    "fingerprint_for",
    "fingerprint_of",
    "headings_by_level",
    "join_pages",
    "list_source_files",
    "markdown",
    "markdown_cache_path",
    "name_order",
    "office",
    "page_count",
    "page_images",
    "page_mark",
    "page_picture",
    "page_sizes",
    "page_starts",
    "page_texts",
    "pages",
    "read_meta",
    "read_pages",
    "retryable_pages",
    "reuse_key",
    "review_seams",
    "same_document",
    "seam",
    "seams_failed",
    "seams_merged",
    "slide_count",
    "slide_seams",
    "split_blocks",
    "strip_page_marks",
    "tidy_markdown",
    "to_markdown",
    "transcribe_office",
    "transcribe_pdf",
    "valid_seams",
    "write_pages",
]
