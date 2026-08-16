from fastapi import APIRouter, File, HTTPException, UploadFile
from loguru import logger

from .. import auth, raw_data, runtime

router = APIRouter(prefix="/api/raw", tags=["raw"], dependencies=[auth.VIEW])


@router.get("")
def listing(access: auth.Access = auth.VIEW) -> dict:
    return raw_data.listing(access.ws)


@router.post("/{kind}", dependencies=[auth.EDIT])
def upload(
    kind: str, files: list[UploadFile] = File(...), access: auth.Access = auth.VIEW
) -> dict:
    try:
        result = raw_data.save(access.ws, kind, files)
    except raw_data.RawError as exc:
        raise HTTPException(404, str(exc)) from exc

    if result["added"]:
        names = ", ".join(f["name"] for f in result["added"])
        logger.info(f"Imported {len(result['added'])} raw file(s) into '{kind}': {names}")
        runtime.bus.publish(
            access.ws.slug, None, "raw.changed", {"kind": kind, "added": len(result["added"])}
        )

    return {**result, "slot": raw_data.slot(access.ws, kind)}


@router.delete("/{kind}/{name}", dependencies=[auth.EDIT])
def delete(kind: str, name: str, access: auth.Access = auth.VIEW) -> dict:
    try:
        result = raw_data.delete(access.ws, kind, name)
    except raw_data.RawError as exc:
        raise HTTPException(404, str(exc)) from exc

    logger.info(f"Removed raw file '{result['deleted']}' from '{kind}'")
    runtime.bus.publish(
        access.ws.slug, None, "raw.changed", {"kind": kind, "deleted": result["deleted"]}
    )
    return {**result, "slot": raw_data.slot(access.ws, kind)}
