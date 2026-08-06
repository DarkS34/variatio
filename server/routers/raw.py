from fastapi import APIRouter, File, HTTPException, UploadFile
from loguru import logger

from .. import raw_data, runtime

router = APIRouter(prefix="/api/raw", tags=["raw"])


@router.get("")
def listing() -> dict:
    return raw_data.listing()


@router.post("/{kind}")
def upload(kind: str, files: list[UploadFile] = File(...)) -> dict:
    try:
        result = raw_data.save(kind, files)
    except raw_data.RawError as exc:
        raise HTTPException(404, str(exc)) from exc

    if result["added"]:
        names = ", ".join(f["name"] for f in result["added"])
        logger.info(f"Imported {len(result['added'])} raw file(s) into '{kind}': {names}")
        runtime.bus.publish(None, "raw.changed", {"kind": kind, "added": len(result["added"])})

    return {**result, "slot": raw_data.slot(kind)}


@router.delete("/{kind}/{name}")
def delete(kind: str, name: str) -> dict:
    try:
        result = raw_data.delete(kind, name)
    except raw_data.RawError as exc:
        raise HTTPException(404, str(exc)) from exc

    logger.info(f"Removed raw file '{result['deleted']}' from '{kind}'")
    runtime.bus.publish(None, "raw.changed", {"kind": kind, "deleted": result["deleted"]})
    return {**result, "slot": raw_data.slot(kind)}
