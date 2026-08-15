"""The raw materials the builders read, listed and written from the browser.

`raw_base_data/` is the user's own data and lives outside the package, so nothing
in the pipeline creates it. A first-time user therefore has an empty chain and no
way to start from the UI; this module is that way in — the two slots, what each one
feeds, and a guarded write into them.
"""

import re
import time
from pathlib import Path

from fastapi import UploadFile

from variant_generator.builders._source_docs import SUPPORTED_EXTS

from . import review, settings

CHUNK = 1024 * 1024
MAX_BYTES = 512 * 1024 * 1024

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


class RawError(Exception):
    pass


def directory(kind: str) -> Path:
    ws = settings.workspace()
    dirs = {CORPUS: ws.raw_corpus_dir, EXEMPLARS: ws.raw_exemplars_dir}
    if kind not in dirs:
        raise RawError(f"Origen desconocido: '{kind}'")
    return dirs[kind]


def listing() -> dict:
    return {
        "supported_extensions": list(SUPPORTED_EXTS),
        "max_bytes": MAX_BYTES,
        "slots": [slot(kind) for kind in SLOTS],
    }


def slot(kind: str) -> dict:
    path = directory(kind)
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


def save(kind: str, uploads: list[UploadFile]) -> dict:
    path = directory(kind)
    path.mkdir(parents=True, exist_ok=True)

    added: list[dict] = []
    rejected: list[dict] = []

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

        target = _free_path(path, name)
        try:
            written = _write(upload, target)
        except RawError as exc:
            target.unlink(missing_ok=True)
            rejected.append({"name": name, "reason": str(exc)})
            continue

        added.append({"name": target.name, "bytes": written, "renamed": target.name != name})

    return {"added": added, "rejected": rejected}


def _write(upload: UploadFile, target: Path) -> int:
    written = 0
    with target.open("wb") as out:
        while True:
            chunk = upload.file.read(CHUNK)
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_BYTES:
                raise RawError(f"Supera el máximo de {MAX_BYTES // (1024 * 1024)} MB")
            out.write(chunk)
    if written == 0:
        raise RawError("El archivo está vacío")
    return written


def delete(kind: str, name: str) -> dict:
    path = directory(kind)
    safe = _safe_name(name)
    target = path / safe
    if not safe or not target.is_file():
        raise RawError(f"No existe '{name}' en {path.name}")
    target.unlink()
    return {"deleted": safe}


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
