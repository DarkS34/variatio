"""The raw documents an instance is built from, and their page transcriptions.

Declares `auth.EDIT` for the whole router, reads included: the raw documents, their
transcriptions and the reader that shows the two side by side are the construction's, and a
student of the subject (`viewer`) opens none of them.

Transcribing early is an ACCELERATOR and never a gate: the `transcribe` job writes no
artifact, nothing is chained after it, and every builder keeps its own conversion phase —
so a build hits the cache when the work is done and does it when it is not.

ROUTE ORDER IS LOAD-BEARING HERE. FastAPI matches in declaration order, so every fixed
`/{kind}/transcription…` path is declared ABOVE `POST /{kind}` and `DELETE /{kind}/{name}`.
Declared the other way round the wildcard swallows them and answers a plausible 404 from a
route nobody meant to call — `DELETE /{kind}/transcription/{name}/{index}` would be read as
deleting a document called "transcription". Do not reorder anything in this file.
"""

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from loguru import logger
from pydantic import BaseModel

from variatio.core import inference

from .. import auth
from ..core import process
from ..pipeline import readings, slots
from . import documents

router = APIRouter(prefix="/api/raw", tags=["raw"], dependencies=[auth.EDIT])


class PageBody(BaseModel):
    """One page's markdown, as the editor corrected it."""

    text: str


class InsertBody(BaseModel):
    """Where a new page goes, and what it says."""

    after: int
    text: str = ""


def _not_found(exc: documents.RawError) -> HTTPException:
    """Turn the library's refusal of an unknown slot or document into a 404."""
    return HTTPException(404, str(exc))


def _transcribing(slug: str, kind: str):
    """Find this slot's transcription job, running or waiting, or nothing."""
    return readings.transcribing(slug, kind)


@router.get("")
def listing(access: auth.Access = auth.EDIT) -> dict:
    """Answer both raw slots with the documents each one holds."""
    return documents.listing(access.ws)


# Every fixed transcription path is declared above the `/{kind}/{name}` wildcards below.
@router.get("/{kind}/transcription")
def transcription(kind: str, access: auth.Access = auth.EDIT) -> dict:
    """Answer one slot's transcription state, per document and with the reason it is stale."""
    try:
        return documents.transcription(access.ws, kind)
    except documents.RawError as exc:
        raise _not_found(exc) from exc


@router.post("/{kind}/transcription")
def start_transcription(kind: str, access: auth.Access = auth.EDIT) -> dict:
    """Queue the transcription of one slot, refusing a second one for the same slot."""
    try:
        documents.directory(access.ws, kind)
    except documents.RawError as exc:
        raise _not_found(exc) from exc

    if not inference.is_available():
        raise HTTPException(
            503,
            f"No hay conexión con el motor de inferencia "
            f"'{inference.engine_name()}'. Arráncalo y vuelve a intentarlo.",
        )

    if _transcribing(access.ws.slug, kind) is not None:
        raise HTTPException(
            409, f"Ya se está transcribiendo «{slots.SLOTS[kind]['label']}»."
        )

    job = process.runner.submit(
        slots.TRANSCRIBE_JOB,
        {"slot": kind},
        workspace=access.ws.slug,
        user_id=access.user.id,
        user_name=access.user.name,
    )
    logger.info(f"[{kind}] Transcripción encolada")
    return {"job": job.to_dict(), "since": process.bus.last_seq}


@router.get("/{kind}/transcription/{name}")
def transcription_document(kind: str, name: str, access: auth.Access = auth.EDIT) -> dict:
    """Answer one document's transcribed pages, each marked failed or empty, and its original.

    The first time an Office document is opened, LibreOffice exports it to PDF inside this
    request (`originals.EXPORT_TIMEOUT_SECONDS` at most); every later opening reads the copy.
    """
    try:
        return documents.transcription_document(access.ws, kind, name)
    except documents.RawError as exc:
        raise _not_found(exc) from exc


@router.get("/{kind}/transcription/{name}/original/{page}")
def original_page(kind: str, name: str, page: int, access: auth.Access = auth.EDIT) -> Response:
    """Answer one page of a document's original as an image.

    Only a document the slot holds, and only a page it has. A page never changes under its
    address — the reader sends the original's version with it — so the browser may keep it.
    """
    try:
        drawn = documents.original_page(access.ws, kind, name, page)
    except documents.RawError as exc:
        raise _not_found(exc) from exc
    if drawn is None:
        raise HTTPException(404, "Esa página no está en el original del documento.")
    data, media_type = drawn
    return Response(
        data, media_type=media_type, headers={"Cache-Control": "private, max-age=604800, immutable"}
    )


@router.post("/{kind}/transcription/{name}")
def insert_page(
    kind: str, name: str, body: InsertBody, access: auth.Access = auth.EDIT
) -> dict:
    """Insert a page after the given index, renumbering what follows."""
    try:
        index = documents.insert_page(access.ws, kind, name, body.after, body.text)
        return {**documents.transcription_document(access.ws, kind, name), "index": index}
    except documents.RawError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put("/{kind}/transcription/{name}/{index}")
def save_page(
    kind: str, name: str, index: int, body: PageBody, access: auth.Access = auth.EDIT
) -> dict:
    """Overwrite one transcribed page by hand.

    A hand-corrected page beats the model and survives every later build: the library
    re-reads from disk on purpose, and an edit does not touch the document's fingerprint.
    """
    try:
        documents.write_page(access.ws, kind, name, index, body.text)
        return documents.transcription_document(access.ws, kind, name)
    except documents.RawError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/{kind}/transcription/{name}/{index}")
def delete_page(
    kind: str, name: str, index: int, access: auth.Access = auth.EDIT
) -> dict:
    """Remove one transcribed page, renumbering what follows.

    The library refuses to remove the last one: a document with zero pages reads as
    `pending`, and the next build would silently throw away every hand correction.
    """
    try:
        documents.delete_page(access.ws, kind, name, index)
        return documents.transcription_document(access.ws, kind, name)
    except documents.RawError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{kind}")
def upload(
    kind: str, files: list[UploadFile] = File(...), access: auth.Access = auth.EDIT
) -> dict:
    """Add documents to one raw slot and answer the slot as it now stands."""
    try:
        result = documents.save(access.ws, kind, files)
    except documents.RawLimitError as exc:
        raise HTTPException(413, str(exc)) from exc
    except documents.RawError as exc:
        raise _not_found(exc) from exc

    if result["added"]:
        names = ", ".join(f["name"] for f in result["added"])
        logger.info(f"[{kind}] {len(result['added'])} documento(s) añadidos: {names}")
        process.bus.publish(
            access.ws.slug, None, "raw.changed", {"kind": kind, "added": len(result["added"])}
        )

    return {**result, "slot": documents.slot(access.ws, kind)}


@router.delete("/{kind}/{name}")
def delete(kind: str, name: str, access: auth.Access = auth.EDIT) -> dict:
    """Remove one raw document. The name is checked against the files the slot holds."""
    try:
        result = documents.delete(access.ws, kind, name)
    except documents.RawError as exc:
        raise _not_found(exc) from exc

    logger.info(f"[{kind}] documento eliminado: {result['deleted']}")
    process.bus.publish(
        access.ws.slug, None, "raw.changed", {"kind": kind, "deleted": result["deleted"]}
    )
    return {**result, "slot": documents.slot(access.ws, kind)}
