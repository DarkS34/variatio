import json
import re
from pathlib import Path

from docling.document_converter import DocumentConverter, InputFormat

SUPPORTED_EXTS = (".pdf", ".docx", ".md", ".txt")
PLAIN_TEXT_EXTS = (".md", ".txt")
CONVERTED_EXTS = (".pdf", ".docx")

CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
SEPARATOR_RE = re.compile(r"^\s*---\s*$", re.MULTILINE)
FENCE_TOKEN_RE = re.compile(r"§§FENCE(\d+)§§")


def default_converter() -> DocumentConverter:
    return DocumentConverter(allowed_formats=[InputFormat.PDF, InputFormat.DOCX])


def list_source_files(input_dir: str | Path) -> list[Path]:
    return sorted(
        p
        for p in Path(input_dir).iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    )


def to_markdown(converter: DocumentConverter, input_path: Path) -> str:
    suffix = input_path.suffix.lower()
    if suffix in PLAIN_TEXT_EXTS:
        return input_path.read_text(encoding="utf-8")
    if suffix in CONVERTED_EXTS:
        return converter.convert(str(input_path)).document.export_to_markdown()
    raise ValueError(f"Unsupported file extension: {suffix}")


def split_blocks(text: str) -> list[str]:
    fences: list[str] = []

    def _stash(match):
        fences.append(match.group(0))
        return f"§§FENCE{len(fences) - 1}§§"

    masked = CODE_FENCE_RE.sub(_stash, text)
    pieces = (
        SEPARATOR_RE.split(masked)
        if SEPARATOR_RE.search(masked)
        else re.split(r"\n\s*\n", masked)
    )

    def _restore(piece: str) -> str:
        return FENCE_TOKEN_RE.sub(lambda m: fences[int(m.group(1))], piece).strip()

    return [restored for restored in (_restore(p) for p in pieces) if restored]


def chunk_text(text: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


def save_json(data: dict, output_file_path: str | Path) -> None:
    output_path = Path(output_file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
