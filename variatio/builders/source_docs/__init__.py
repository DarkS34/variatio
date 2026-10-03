"""Reading a source document: files, markdown, chunking and page transcription.

Shared by all three builders — anything about reading a source file belongs here and is
never duplicated into one of them. `pages` is the only module of the four that talks to a
model; `markdown` and `chunking` import neither `inference` nor `progress`, which is the
property the split exists to keep checkable; `office` talks to LibreOffice and to no model.

Not private, despite serving the builders: `entrypoints/transcribe.py`, `server/raw_data.py`,
`server/db/repository.py`, `evaluation/raw_text.py`, the settings registry and fourteen
tests all reach it. `_context.py` beside it keeps its underscore, being genuinely the
builders' own.
"""

from . import chunking, files, markdown, office, pages
from .office import slide_count
from .chunking import chunk_markdown, chunk_sections, chunk_text
from .files import (
    CONVERTED_EXTS,
    OFFICE_EXTS,
    PLAIN_TEXT_EXTS,
    SUPPORTED_EXTS,
    LazyConverter,
    default_converter,
    list_source_files,
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
from .pages import (
    PARAGRAPH,
    FAILED_PAGE_PREFIXES,
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
    "office",
    "page_count",
    "page_images",
    "page_mark",
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
