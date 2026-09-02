"""Finding source documents, identifying them, and building a converter for them."""

import hashlib
from pathlib import Path

SUPPORTED_EXTS = (".pdf", ".docx", ".pptx", ".md", ".txt")
PLAIN_TEXT_EXTS = (".md", ".txt")
CONVERTED_EXTS = (".pdf", ".docx", ".pptx")
# What Docling reads as a declared structure rather than as a page to render: the two
# Office formats. Their pictures are read apart, one model call each — see `pages.py`.
OFFICE_EXTS = (".docx", ".pptx")


def source_hash(path: str | Path) -> str:
    """Return the SHA-256 of a source document, which is what identifies it.

    A timestamp is not: copying a workspace, restoring a backup or checking the tree out
    again rewrites every mtime without changing a byte, and a cached page costs one model
    call per page to rebuild.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def default_converter(ocr: bool = False, table_structure: bool = True):
    """Build a Docling converter for PDF, DOCX and PPTX.

    Raises ImportError naming the `builders` extra when Docling is not installed. The PDF
    pipeline is what costs — the layout models, and `cv2` behind `table_structure` — and
    Docling builds it on the first PDF it converts, so an Office file never pays for it.
    """
    # Imported here and NEVER at module scope: the runtime pipeline does not install the
    # `builders` extra, and these imports cost ~700 MB (torch, transformers, opencv).
    try:
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import (
            DocumentConverter,
            InputFormat,
            PdfFormatOption,
        )
    except ImportError as e:
        raise ImportError(
            "The builders need Docling, which is an optional extra. "
            "Install it with: uv sync --extra builders"
        ) from e

    pdf_options = PdfPipelineOptions()
    pdf_options.do_ocr = ocr
    pdf_options.do_table_structure = table_structure

    return DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.DOCX, InputFormat.PPTX],
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pdf_options, backend=PyPdfiumDocumentBackend
            )
        },
    )


class LazyConverter:
    """A converter built on first real USE and never at import.

    A callable holder rather than a property, which is what makes the laziness reach the
    normal case: a corpus of PDFs goes through the page-transcription route and converts
    nothing, and a corpus whose markdown is already cached does not convert either.
    """

    def __init__(self, **options):
        """Remember the converter options without building anything."""
        self._options = options
        self._converter = None

    def __call__(self):
        """Return the converter, building it the first time it is asked for."""
        if self._converter is None:
            self._converter = default_converter(**self._options)
        return self._converter


def resolve_converter(converter):
    """Return a converter, opening a lazy holder if that is what arrived.

    `DocumentConverter` exposes `convert` and no `__call__`, so the two cannot be confused.
    """
    return converter() if callable(converter) else converter


def list_source_files(input_dir: str | Path, recursive: bool = False) -> list[Path]:
    """List the supported documents of a directory, in a stable order.

    A slot that is not there lists nothing rather than raising, whichever way it is walked.
    Every caller handles the empty case with a message naming the directory, and `rglob`
    already answered that way while `iterdir` raised — so a renamed or never-created slot
    surfaced as a traceback out of a build worker instead of the message written for it.
    """
    root = Path(input_dir)
    if not root.is_dir():
        return []
    candidates = root.rglob("*") if recursive else root.iterdir()
    return sorted(p for p in candidates if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS)


def required_cache_dir(cache_dir: str | Path | None, what: str) -> Path:
    """Return the cache directory, refusing to guess one when none was given.

    Nothing may fall back to a workspace nobody named: a silent default had a build of one
    instance read and write its derivations under another's tree. A caller with no cache
    says so with `use_cache=False`.
    """
    if cache_dir is None:
        raise ValueError(
            f"{what} needs an explicit cache_dir (a workspace's markdown_cache_dir); "
            "pass use_cache=False if there is no cache to use."
        )
    return Path(cache_dir)
