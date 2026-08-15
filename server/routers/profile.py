from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import auth
from ..editors import profile_edit
from .pipeline import get_pipeline

router = APIRouter(prefix="/api/profile", tags=["profile"], dependencies=[auth.VIEW])


class ProfileBody(BaseModel):
    profile: dict


@router.get("")
def read() -> dict:
    return profile_edit.load()


@router.post("/validate", dependencies=[auth.EDIT])
def validate(body: ProfileBody) -> dict:
    error = profile_edit.validate(body.profile)
    return {"valid": error is None, "error": error}


@router.put("", dependencies=[auth.EDIT])
def save(body: ProfileBody) -> dict:
    try:
        result = profile_edit.save(body.profile)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, "pipeline": get_pipeline()}
