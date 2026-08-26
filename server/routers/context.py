from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from variatio.instance.content_context import CANONICAL_KEYS

from .. import auth
from ..editors import context_edit

router = APIRouter(prefix="/api/context", tags=["context"], dependencies=[auth.VIEW])


class ContextBody(BaseModel):
    narrative: str = ""
    facts: dict[str, str] = Field(default_factory=dict)


@router.get("")
def read_context(access: auth.Access = auth.VIEW) -> dict:
    return {**context_edit.load(access.ws), "canonical_keys": list(CANONICAL_KEYS)}


@router.put("", dependencies=[auth.EDIT])
def write_context(body: ContextBody, access: auth.Access = auth.VIEW) -> dict:
    facts = {key: value.strip() for key, value in body.facts.items() if value.strip()}
    return context_edit.save(access.ws, body.narrative.strip(), facts)


@router.post("/adopt-draft", dependencies=[auth.EDIT])
def adopt_draft(access: auth.Access = auth.VIEW) -> dict:
    try:
        return context_edit.adopt_draft(access.ws)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
