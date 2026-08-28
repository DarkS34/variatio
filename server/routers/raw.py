from fastapi import APIRouter, File, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel

from variatio.core import inference

from .. import auth, raw_data, runtime

router = APIRouter(prefix="/api/raw", tags=["raw"], dependencies=[auth.VIEW])


class PageBody(BaseModel):
    text: str


class InsertBody(BaseModel):
    after: int
    text: str = ""


def _not_found(exc: raw_data.RawError) -> HTTPException:
    return HTTPException(404, str(exc))


def _transcribing(slug: str, kind: str):
    for job in runtime.runner.running(slug) + runtime.runner.pending(slug):
        if job.kind == raw_data.TRANSCRIBE_JOB and job.params.get("slot") == kind:
            return job
    return None


@router.get("")
def listing(access: auth.Access = auth.VIEW) -> dict:
    return raw_data.listing(access.ws)


@router.get("/{kind}/transcription")
def transcription(kind: str, access: auth.Access = auth.VIEW) -> dict:
    try:
        return raw_data.transcription(access.ws, kind)
    except raw_data.RawError as exc:
        raise _not_found(exc) from exc


@router.post("/{kind}/transcription", dependencies=[auth.EDIT])
def start_transcription(kind: str, access: auth.Access = auth.VIEW) -> dict:
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

    job = runtime.runner.submit(
        raw_data.TRANSCRIBE_JOB,
        {"slot": kind},
        workspace=access.ws.slug,
        user_id=access.user.id,
        user_name=access.user.name,
    )
    logger.info(f"[{kind}] Transcripción encolada")
    return {"job": job.to_dict(), "since": runtime.bus.last_seq}


@router.get("/{kind}/transcription/{name}")
def transcription_document(kind: str, name: str, access: auth.Access = auth.VIEW) -> dict:
    try:
        return raw_data.transcription_document(access.ws, kind, name)
    except raw_data.RawError as exc:
        raise _not_found(exc) from exc


@router.post("/{kind}/transcription/{name}", dependencies=[auth.EDIT])
def insert_page(
    kind: str, name: str, body: InsertBody, access: auth.Access = auth.VIEW
) -> dict:
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
    try:
        result = raw_data.save(access.ws, kind, files)
    except raw_data.RawLimitError as exc:
        raise HTTPException(413, str(exc)) from exc
    except raw_data.RawError as exc:
        raise _not_found(exc) from exc

    if result["added"]:
        names = ", ".join(f["name"] for f in result["added"])
        logger.info(f"[{kind}] {len(result['added'])} documento(s) añadidos: {names}")
        runtime.bus.publish(
            access.ws.slug, None, "raw.changed", {"kind": kind, "added": len(result["added"])}
        )

    return {**result, "slot": raw_data.slot(access.ws, kind)}


@router.delete("/{kind}/{name}", dependencies=[auth.EDIT])
def delete(kind: str, name: str, access: auth.Access = auth.VIEW) -> dict:
    try:
        result = raw_data.delete(access.ws, kind, name)
    except raw_data.RawError as exc:
        raise _not_found(exc) from exc

    logger.info(f"[{kind}] documento eliminado: {result['deleted']}")
    runtime.bus.publish(
        access.ws.slug, None, "raw.changed", {"kind": kind, "deleted": result["deleted"]}
    )
    return {**result, "slot": raw_data.slot(access.ws, kind)}
