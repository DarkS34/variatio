"""The subject's context: what this instance is about, in prose plus three named facts.

Declares `auth.VIEW` for the whole router; the two writes add `auth.EDIT`. It is not a
stage — nobody approves it and it is absent from `review.ARTIFACTS` — so it is read and
edited from the panel rather than from a stage screen.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from variatio.instance.content_context import CANONICAL_KEYS

from .. import auth
from ..editors import context_edit

router = APIRouter(prefix="/api/context", tags=["context"], dependencies=[auth.VIEW])


class ContextBody(BaseModel):
    """The narrative and the named facts, as the panel's form sends them."""

    narrative: str = ""
    facts: dict[str, str] = Field(default_factory=dict)


@router.get("")
def read_context(access: auth.Access = auth.VIEW) -> dict:
    """Answer the curated context, plus the fact keys the prompts address by name."""
    return {**context_edit.load(access.ws), "canonical_keys": list(CANONICAL_KEYS)}


@router.put("", dependencies=[auth.EDIT])
def write_context(body: ContextBody, access: auth.Access = auth.VIEW) -> dict:
    """Save the curated context, dropping every fact whose value is blank."""
    facts = {key: value.strip() for key, value in body.facts.items() if value.strip()}
    return context_edit.save(access.ws, body.narrative.strip(), facts)


@router.post("/adopt-draft", dependencies=[auth.EDIT])
def adopt_draft(access: auth.Access = auth.VIEW) -> dict:
    """Promote the last build's synthesis over the curated file."""
    try:
        return context_edit.adopt_draft(access.ws)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
