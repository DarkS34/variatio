"""Reading a source document: files, markdown, chunking and page transcription.

Shared by all three builders — anything about reading a source file belongs here and is
never duplicated into one of them. `pages` is the only module of the four that talks to a
model; `markdown` and `chunking` import neither `inference` nor `progress`, which is the
property the split exists to keep checkable.
"""

from . import chunking, files, markdown, pages
from .chunking import chunk_markdown, chunk_sections, chunk_text
from .files import (
    CONVERTED_EXTS,
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
    review_seams,
    same_document,
    seam,
    seams_failed,
    seams_merged,
    transcribe_pdf,
    valid_seams,
    write_pages,
)

__all__ = [
    "CONVERTED_EXTS",
    "PARAGRAPH",
    "PLAIN_TEXT_EXTS",
    "SUPPORTED_EXTS",
    "LazyConverter",
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
    "page_count",
    "page_images",
    "page_mark",
    "pages",
    "read_meta",
    "read_pages",
    "review_seams",
    "same_document",
    "seam",
    "seams_failed",
    "seams_merged",
    "split_blocks",
    "strip_page_marks",
    "tidy_markdown",
    "to_markdown",
    "transcribe_pdf",
    "valid_seams",
    "write_pages",
]
