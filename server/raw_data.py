"""The raw materials the builders read, listed and written from the browser.

A workspace's `raw/` is the user's own data and lives outside the package, so nothing
in the pipeline creates its contents. A first-time user therefore has an empty chain and no
way to start from the UI; this module is that way in — the two slots, what each one
feeds, a guarded write into them, and the transcription of what they hold into markdown
pages that a person can then correct by hand.
"""

import re
import time
from pathlib import Path

from fastapi import UploadFile

from variatio.builders._source_docs import SUPPORTED_EXTS
from variatio.core.workspace import Workspace

from . import review

CHUNK = 1024 * 1024
MAX_BYTES = 512 * 1024 * 1024
MAX_FILES = 100
MAX_REQUEST_BYTES = 1024 * 1024 * 1024
MAX_SLOT_BYTES = 4 * 1024 * 1024 * 1024

CORPUS = "corpus"
EXEMPLARS = "exemplars"

SLOTS: dict[str, dict] = {
    CORPUS: {
        "kind": CORPUS,
        "label": "Corpus del dominio",
        "purpose": (
            "Los apuntes y el material teórico de la asignatura. De aquí se extrae el "
            "grafo de conocimiento: conceptos, dominios y relaciones."
        ),
        "feeds": [review.KNOWLEDGE_GRAPH],
    },
    EXEMPLARS: {
        "kind": EXEMPLARS,
        "label": "Ejemplares en bruto",
        "purpose": (
            "Ejercicios, exámenes o prácticas ya resueltos. De aquí se infiere el perfil "
            "de contenido y se extrae el banco de ejemplos."
        ),
        "feeds": [review.EXEMPLARS_PROFILE, review.EXEMPLARS_BANK],
    },
}

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

TRANSCRIBE_JOB = "transcribe"


class RawError(Exception):
    pass


class RawLimitError(RawError):
    pass


def directory(ws: Workspace, kind: str) -> Path:
    dirs = {CORPUS: ws.raw_corpus_dir, EXEMPLARS: ws.raw_exemplars_dir}
    if kind not in dirs:
        raise RawError(f"Origen desconocido: '{kind}'")
    return dirs[kind]


def listing(ws: Workspace) -> dict:
    return {
        "supported_extensions": list(SUPPORTED_EXTS),
        "max_bytes": MAX_BYTES,
        "max_files": MAX_FILES,
        "max_request_bytes": MAX_REQUEST_BYTES,
        "max_slot_bytes": MAX_SLOT_BYTES,
        "slots": [slot(ws, kind) for kind in SLOTS],
    }


def slot(ws: Workspace, kind: str) -> dict:
    path = directory(ws, kind)
    files = _files(path)
    return {
        **SLOTS[kind],
        "path": str(path),
        "exists": path.is_dir(),
        "files": files,
        "bytes": sum(f["bytes"] for f in files),
    }


def _files(path: Path) -> list[dict]:
    if not path.is_dir():
        return []
    out = []
    for entry in sorted(path.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_file() or entry.suffix.lower() not in SUPPORTED_EXTS:
            continue
        stat = entry.stat()
        out.append(
            {
                "name": entry.name,
                "bytes": stat.st_size,
                "modified": stat.st_mtime,
                "extension": entry.suffix.lower(),
            }
        )
    return out


def save(ws: Workspace, kind: str, uploads: list[UploadFile]) -> dict:
    path = directory(ws, kind)
    if len(uploads) > MAX_FILES:
        raise RawLimitError(
            f"Son {len(uploads)} archivos y el máximo por envío es {MAX_FILES}: "
            "súbelos en varias tandas."
        )
    path.mkdir(parents=True, exist_ok=True)

    added: list[dict] = []
    rejected: list[dict] = []
    request_left = MAX_REQUEST_BYTES
    # Counted against what the slot already holds, or the cap is walked past one
    # request at a time.
    slot_left = MAX_SLOT_BYTES - _slot_bytes(path)

    for upload in uploads:
        name = _safe_name(upload.filename or "")
        if not name:
            rejected.append({"name": upload.filename or "?", "reason": "Nombre de archivo no válido"})
            continue
        if Path(name).suffix.lower() not in SUPPORTED_EXTS:
            rejected.append(
                {"name": name, "reason": f"Extensión no admitida ({', '.join(SUPPORTED_EXTS)})"}
            )
            continue

        limit, reason = _budget(request_left, slot_left)
        target = _free_path(path, name)
        try:
            written = _write(upload, target, limit, reason)
        except RawError as exc:
            target.unlink(missing_ok=True)
            rejected.append({"name": name, "reason": str(exc)})
            continue

        request_left -= written
        slot_left -= written
        added.append({"name": target.name, "bytes": written, "renamed": target.name != name})

    return {"added": added, "rejected": rejected}


def _slot_bytes(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(entry.stat().st_size for entry in path.iterdir() if entry.is_file())


def _budget(request_left: int, slot_left: int) -> tuple[int, str]:
    options = [
        (MAX_BYTES, f"Supera el máximo de {_mb(MAX_BYTES)} MB por archivo"),
        (request_left, f"El envío supera el máximo de {_mb(MAX_REQUEST_BYTES)} MB en total"),
        (
            slot_left,
            f"El origen supera el máximo de {_gb(MAX_SLOT_BYTES)} GB: "
            "borra documentos antes de subir más",
        ),
    ]
    return min(options, key=lambda option: option[0])


def _mb(size: int) -> int:
    return size // (1024 * 1024)


def _gb(size: int) -> int:
    return size // (1024 * 1024 * 1024)


def _write(upload: UploadFile, target: Path, limit: int, reason: str) -> int:
    written = 0
    with target.open("wb") as out:
        while True:
            chunk = upload.file.read(CHUNK)
            if not chunk:
                break
            written += len(chunk)
            if written > limit:
                raise RawError(reason)
            out.write(chunk)
    if written == 0:
        raise RawError("El archivo está vacío")
    return written


def delete(ws: Workspace, kind: str, name: str) -> dict:
    path = directory(ws, kind)
    safe = _safe_name(name)
    target = path / safe
    if not safe or not target.is_file():
        raise RawError(f"No existe '{name}' en {path.name}")
    target.unlink()
    return {"deleted": safe}


def _stage():
    from variatio.stages import transcribe

    return transcribe


def document(ws: Workspace, kind: str, name: str) -> str:
    path = directory(ws, kind)
    safe = _safe_name(name)
    if not safe or safe not in {entry["name"] for entry in _files(path)}:
        raise RawError(f"No existe '{name}' en {path.name}")
    return safe


def transcription(ws: Workspace, kind: str) -> dict:
    directory(ws, kind)
    return _stage().transcription_status(ws, kind)


def transcription_document(ws: Workspace, kind: str, name: str) -> dict:
    safe = document(ws, kind, name)
    return {"name": safe, "pages": _stage().document_pages_listing(ws, kind, safe)}


def write_page(ws: Workspace, kind: str, name: str, index: int, text: str) -> None:
    _stage().write_document_page(ws, kind, document(ws, kind, name), index, text)


def insert_page(ws: Workspace, kind: str, name: str, after: int, text: str) -> int:
    return _stage().insert_document_page(ws, kind, document(ws, kind, name), after, text)


def delete_page(ws: Workspace, kind: str, name: str, index: int) -> None:
    _stage().delete_document_page(ws, kind, document(ws, kind, name), index)


def _safe_name(name: str) -> str:
    base = Path(name.replace("\\", "/")).name.strip()
    base = _UNSAFE.sub("_", base).strip(". ")
    return base[:180]


def _free_path(directory_path: Path, name: str) -> Path:
    target = directory_path / name
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    for index in range(2, 100):
        candidate = directory_path / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
    return directory_path / f"{stem} ({int(time.time())}){suffix}"
