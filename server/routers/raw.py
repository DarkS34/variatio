"""The raw documents an instance is built from, and their page transcriptions.

Declares `auth.VIEW` for the whole router; uploading, deleting and every transcription
write add `auth.EDIT`.

Transcribing early is an ACCELERATOR and never a gate: the `transcribe` job writes no
artifact, nothing is chained after it, and every builder keeps its own conversion phase —
so a build hits the cache when the work is done and does it when it is not.

ROUTE ORDER IS LOAD-BEARING HERE. FastAPI matches in declaration order, so every fixed
`/{kind}/transcription…` path is declared ABOVE `POST /{kind}` and `DELETE /{kind}/{name}`.
Declared the other way round the wildcard swallows them and answers a plausible 404 from a
route nobody meant to call — `DELETE /{kind}/transcription/{name}/{index}` would be read as
deleting a document called "transcription". Do not reorder anything in this file.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel

from variatio.core import inference

from .. import auth, raw_data, singletons

router = APIRouter(prefix="/api/raw", tags=["raw"], dependencies=[auth.VIEW])


class PageBody(BaseModel):
    """One page's markdown, as the editor corrected it."""

    text: str


class InsertBody(BaseModel):
    """Where a new page goes, and what it says."""

    after: int
    text: str = ""


def _not_found(exc: raw_data.RawError) -> HTTPException:
    """Turn the library's refusal of an unknown slot or document into a 404."""
    return HTTPException(404, str(exc))


def _transcribing(slug: str, kind: str):
    """Find this slot's transcription job, running or waiting, or nothing."""
    return singletons.transcribing(slug, kind)


@router.get("")
def listing(access: auth.Access = auth.VIEW) -> dict:
    """Answer both raw slots with the documents each one holds."""
    return raw_data.listing(access.ws)


# Every fixed transcription path is declared above the `/{kind}/{name}` wildcards below.
@router.get("/{kind}/transcription")
def transcription(kind: str, access: auth.Access = auth.VIEW) -> dict:
    """Answer one slot's transcription state, per document and with the reason it is stale."""
    try:
        return raw_data.transcription(access.ws, kind)
    except raw_data.RawError as exc:
        raise _not_found(exc) from exc


@router.post("/{kind}/transcription", dependencies=[auth.EDIT])
def start_transcription(kind: str, access: auth.Access = auth.VIEW) -> dict:
    """Queue the transcription of one slot, refusing a second one for the same slot."""
    try:
        raw_data.directory(access.ws, kind)
    except raw_data.RawError as exc:
        raise _not_found(exc) from exc

    if not inference.is_available():
        raise HTTPException(
            503,
            f"No hay conexión con el motor de inferencia "
            f"'{inference.engine_name()}'. Arráncalo y vuelve a intentarlo.",
        )

    if _transcribing(access.ws.slug, kind) is not None:
        raise HTTPException(
            409, f"Ya se está transcribiendo «{raw_data.SLOTS[kind]['label']}»."
        )

    job = singletons.runner.submit(
        raw_data.TRANSCRIBE_JOB,
        {"slot": kind},
        workspace=access.ws.slug,
        user_id=access.user.id,
        user_name=access.user.name,
    )
    logger.info(f"[{kind}] Transcripción encolada")
    return {"job": job.to_dict(), "since": singletons.bus.last_seq}


@router.get("/{kind}/transcription/{name}")
def transcription_document(kind: str, name: str, access: auth.Access = auth.VIEW) -> dict:
    """Answer one document's transcribed pages, each marked failed or empty."""
    try:
        return raw_data.transcription_document(access.ws, kind, name)
    except raw_data.RawError as exc:
        raise _not_found(exc) from exc


@router.post("/{kind}/transcription/{name}", dependencies=[auth.EDIT])
def insert_page(
    kind: str, name: str, body: InsertBody, access: auth.Access = auth.VIEW
) -> dict:
    """Insert a page after the given index, renumbering what follows."""
    try:
        index = raw_data.insert_page(access.ws, kind, name, body.after, body.text)
        return {**raw_data.transcription_document(access.ws, kind, name), "index": index}
    except raw_data.RawError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put("/{kind}/transcription/{name}/{index}", dependencies=[auth.EDIT])
def save_page(
    kind: str, name: str, index: int, body: PageBody, access: auth.Access = auth.VIEW
) -> dict:
    """Overwrite one transcribed page by hand.

    A hand-corrected page beats the model and survives every later build: the library
    re-reads from disk on purpose, and an edit does not touch the document's fingerprint.
    """
    try:
        raw_data.write_page(access.ws, kind, name, index, body.text)
        return raw_data.transcription_document(access.ws, kind, name)
    except raw_data.RawError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/{kind}/transcription/{name}/{index}", dependencies=[auth.EDIT])
def delete_page(
    kind: str, name: str, index: int, access: auth.Access = auth.VIEW
) -> dict:
    """Remove one transcribed page, renumbering what follows.

    The library refuses to remove the last one: a document with zero pages reads as
    `pending`, and the next build would silently throw away every hand correction.
    """
    try:
        raw_data.delete_page(access.ws, kind, name, index)
        return raw_data.transcription_document(access.ws, kind, name)
    except raw_data.RawError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{kind}", dependencies=[auth.EDIT])
def upload(
    kind: str, files: list[UploadFile] = File(...), access: auth.Access = auth.VIEW
) -> dict:
    """Add documents to one raw slot and answer the slot as it now stands."""
    try:
        result = raw_data.save(access.ws, kind, files)
    except raw_data.RawLimitError as exc:
        raise HTTPException(413, str(exc)) from exc
    except raw_data.RawError as exc:
        raise _not_found(exc) from exc

    if result["added"]:
        names = ", ".join(f["name"] for f in result["added"])
        logger.info(f"[{kind}] {len(result['added'])} documento(s) añadidos: {names}")
        singletons.bus.publish(
            access.ws.slug, None, "raw.changed", {"kind": kind, "added": len(result["added"])}
        )

    return {**result, "slot": raw_data.slot(access.ws, kind)}


@router.delete("/{kind}/{name}", dependencies=[auth.EDIT])
def delete(kind: str, name: str, access: auth.Access = auth.VIEW) -> dict:
    """Remove one raw document. The name is checked against the files the slot holds."""
    try:
        result = raw_data.delete(access.ws, kind, name)
    except raw_data.RawError as exc:
        raise _not_found(exc) from exc

    logger.info(f"[{kind}] documento eliminado: {result['deleted']}")
    singletons.bus.publish(
        access.ws.slug, None, "raw.changed", {"kind": kind, "deleted": result["deleted"]}
    )
    return {**result, "slot": raw_data.slot(access.ws, kind)}
