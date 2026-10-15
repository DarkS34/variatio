"""The raw reading the RAG arm retrieves over: every document of a slot, as plain text.

Deliberately NOT the pipeline's transcription. The page cache under `cache/markdown/` is
written by a vision model page by page, with the seams decided by a second call and the
pictures read one by one — all of it this system's work, and a baseline built with this
system's reading is not a baseline. What a competent engineer has without this TFM is a
plain extractor: `pypdf` on a PDF, `python-docx` and `python-pptx` on an Office file, the
bytes of a `.md` or `.txt` as they are. Tables lose their columns, formulas lose their
symbols and a scanned page yields nothing. That is the honest lower bound and it is kept
on purpose.

The reading is prepared inside step 1 of the construction — on upload, on deletion and at
the head of the `transcribe` job — and it announces nothing: no step, no badge, no state on
the screen. `prepare_slot` reconciles a slot against what is on disk, keyed by the bytes of
each file, so it costs nothing when nothing changed and the arm can call it again at
retrieval time to catch up a subject prepared before this existed.
"""

import hashlib
import json
from pathlib import Path

from loguru import logger

from variatio.builders.source_docs.chunking import chunk_text
from variatio.builders.source_docs.files import list_source_files
from variatio.core.json_io import write_json
from variatio.entrypoints.transcribe import SLOTS, slot_dir

TEXT_VERSION = 1
META_NAME = "_meta.json"


def prepare_workspace(ws) -> dict[str, dict]:
    """Reconcile both slots; one result per slot."""
    return {slot: prepare_slot(ws, slot) for slot in SLOTS}


def prepare_slot(ws, slot: str) -> dict:
    """Bring the slot's plain readings in line with its files: read the new, drop the gone.

    A file is its bytes, so a rename re-keys and a re-upload of the same document costs
    nothing. A document the extractor cannot read is logged and left out — a plain RAG
    simply does not have it — and never stops the others.
    """
    root = text_dir(ws, slot)
    meta = _read_meta(root)
    sources = list_source_files(slot_dir(ws, slot))
    present = {source.name for source in sources}

    read = 0
    failed: list[str] = []
    for source in sources:
        digest = _sha256(source)
        entry = meta.get(source.name)
        if entry and entry.get("sha256") == digest and (root / entry["file"]).is_file():
            continue
        try:
            text = read_document(source)
        except Exception as exc:  # noqa: BLE001 - one unreadable file must not stop the slot
            logger.warning(f"[rag] No se pudo leer «{source.name}» en crudo: {exc}")
            failed.append(source.name)
            meta.pop(source.name, None)
            continue
        target = root / f"{source.name}.txt"
        root.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        meta[source.name] = {
            "sha256": digest,
            "file": target.name,
            "chars": len(text),
            "version": TEXT_VERSION,
        }
        read += 1

    dropped = [name for name in list(meta) if name not in present]
    for name in dropped:
        stale = root / meta.pop(name)["file"]
        stale.unlink(missing_ok=True)

    if read or dropped or failed:
        root.mkdir(parents=True, exist_ok=True)
        write_json(root / META_NAME, meta)
        logger.info(
            f"[rag] Lectura en crudo de «{slot}» en «{ws.slug}»: "
            f"{read} leído(s), {len(dropped)} retirado(s), {len(failed)} ilegible(s)"
        )
    return {"read": read, "dropped": len(dropped), "failed": failed, "documents": len(meta)}


def chunks(ws, slot: str, max_chars: int) -> dict[str, str]:
    """Cut every reading of a slot into pieces, keyed `"document"#n` with n from 1.

    The key is what the session records as `exemplar_ids` and what the prompt prints above
    each piece, so a reader of a recorded session can open the document and find it.
    """
    out: dict[str, str] = {}
    for name, text in texts(ws, slot).items():
        for index, piece in enumerate(chunk_text(text, max_chars), start=1):
            out[f"{name}#{index}"] = piece
    return out


def texts(ws, slot: str) -> dict[str, str]:
    """Return every prepared reading of a slot, keyed by document name, in a stable order."""
    root = text_dir(ws, slot)
    out: dict[str, str] = {}
    for name, entry in sorted(_read_meta(root).items()):
        path = root / entry["file"]
        if path.is_file():
            out[name] = path.read_text(encoding="utf-8")
    return out


def text_dir(ws, slot: str) -> Path:
    """Where one slot's plain readings live, beside the pipeline's caches and apart from them."""
    if slot not in SLOTS:
        raise ValueError(f"Unknown slot '{slot}'; expected one of {list(SLOTS)}")
    return ws.cache_dir / "rag_text" / slot


# READERS -----------------------------------------------------------------------------------


def read_document(source: Path) -> str:
    """Return a document's plain text with the plainest extractor there is for its type."""
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(source)
    if suffix == ".docx":
        return _read_docx(source)
    if suffix == ".pptx":
        return _read_pptx(source)
    return source.read_text(encoding="utf-8", errors="replace")


def _read_pdf(source: Path) -> str:
    """Extract the text layer of every page with pypdf, pages separated by a blank line.

    pypdf warns once per embedded font that `fontTools` would parse its encoding better;
    over the reference PDFs those warnings are the whole output and the text is fine, so
    they are lowered to what the job log does not carry.
    """
    import logging

    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(str(source))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(page for page in pages if page)


def _read_docx(source: Path) -> str:
    """Return the paragraphs and table cells of a Word file, in document order."""
    from docx import Document

    document = Document(str(source))
    parts = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n\n".join(parts)


def _read_pptx(source: Path) -> str:
    """Return the text of every shape of every slide, slides separated by a blank line."""
    from pptx import Presentation

    slides: list[str] = []
    for slide in Presentation(str(source)).slides:
        lines = [
            shape.text_frame.text.strip()
            for shape in slide.shapes
            if shape.has_text_frame and shape.text_frame.text.strip()
        ]
        if lines:
            slides.append("\n".join(lines))
    return "\n\n".join(slides)


# META --------------------------------------------------------------------------------------


def _read_meta(root: Path) -> dict[str, dict]:
    """Read the slot's meta, answering an empty one for a missing or unreadable file."""
    path = root / META_NAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _sha256(path: Path) -> str:
    """Hash a file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
