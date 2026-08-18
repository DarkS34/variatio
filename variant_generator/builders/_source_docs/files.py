from pathlib import Path

SUPPORTED_EXTS = (".pdf", ".docx", ".md", ".txt")
PLAIN_TEXT_EXTS = (".md", ".txt")
CONVERTED_EXTS = (".pdf", ".docx")


def default_converter(ocr: bool = False, table_structure: bool = True):
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
        allowed_formats=[InputFormat.PDF, InputFormat.DOCX],
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pdf_options, backend=PyPdfiumDocumentBackend
            )
        },
    )


def list_source_files(input_dir: str | Path, recursive: bool = False) -> list[Path]:
    root = Path(input_dir)
    candidates = root.rglob("*") if recursive else root.iterdir()
    return sorted(p for p in candidates if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS)


# `cache_dir` is required everywhere it appears: it used to fall back to the default
# workspace, so a build of instance B could read and write B's derivations under A's tree.
# Every caller resolves it from its own `Workspace`, and a caller that has no cache says so
# with `use_cache=False`.
def required_cache_dir(cache_dir: str | Path | None, what: str) -> Path:
    if cache_dir is None:
        raise ValueError(
            f"{what} needs an explicit cache_dir (a workspace's markdown_cache_dir); "
            "pass use_cache=False if there is no cache to use."
        )
    return Path(cache_dir)
