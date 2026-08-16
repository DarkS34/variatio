from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import auth
from ..editors import profile_edit
from .pipeline import pipeline_payload

router = APIRouter(prefix="/api/profile", tags=["profile"], dependencies=[auth.VIEW])


class ProfileBody(BaseModel):
    profile: dict


@router.get("")
def read(access: auth.Access = auth.VIEW) -> dict:
    return profile_edit.load(access.ws)


@router.post("/validate", dependencies=[auth.EDIT])
def validate(body: ProfileBody) -> dict:
    error = profile_edit.validate(body.profile)
    return {"valid": error is None, "error": error}


@router.put("", dependencies=[auth.EDIT])
def save(body: ProfileBody, access: auth.Access = auth.VIEW) -> dict:
    try:
        result = profile_edit.save(access.ws, body.profile)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, "pipeline": pipeline_payload(access)}
