"""The exemplars bank: the items an instance learns its shapes from.

Declares `auth.VIEW` for the whole router; every write adds `auth.EDIT`. Each write
answers with the chain's new state, so a screen never has to ask for it separately.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .. import auth
from ..editors import bank_edit
from ..editors.bank_edit import BankError
from .pipeline import pipeline_payload

router = APIRouter(prefix="/api/bank", tags=["bank"], dependencies=[auth.VIEW])


class PatchBody(BaseModel):
    """The subset of an item's fields being rewritten."""

    fields: dict


class ConceptsBody(BaseModel):
    """An item's concept tags, with which of them the item is actually about."""

    concepts: list[str]
    primary_concept: str | None = None


@router.get("")
def listing(
    concept: str | None = None,
    untagged: bool | None = None,
    q: str | None = None,
    source: str | None = None,
    item_type: str | None = None,
    order: str = Query("id", pattern="^(suspicion|id|recent)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    access: auth.Access = auth.VIEW,
) -> dict:
    """Answer one page of the bank, filtered and ordered as asked.

    A modality the profile does not declare is a 422 naming it, never an empty page: the
    filter is an equality, so an unknown value would read as «the bank has none of these»
    rather than «that does not exist». The 404 of this route means «there is no bank yet».
    """
    try:
        result = bank_edit.listing(
            access.ws,
            concept=concept,
            untagged=untagged,
            query=q,
            source=source,
            item_type=item_type,
            order=order,
            page=page,
            page_size=page_size,
        )
    except BankError as exc:
        raise HTTPException(404, str(exc)) from exc

    declared = [t["key"] for t in result["item_types"]]
    if item_type and item_type not in declared:
        raise HTTPException(
            422,
            f"El perfil de ejemplares no declara la modalidad «{item_type}»; "
            f"las que hay: {', '.join(declared) or 'ninguna'}",
        )
    return result


@router.get("/coverage")
def coverage(access: auth.Access = auth.VIEW) -> dict:
    """Answer how much of the graph the bank's tags actually reach."""
    try:
        return bank_edit.coverage(access.ws)
    except BankError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch("/{item_id}", dependencies=[auth.EDIT])
def patch(item_id: str, body: PatchBody, access: auth.Access = auth.VIEW) -> dict:
    """Rewrite some of an item's fields."""
    try:
        result = bank_edit.patch_item(access.ws, item_id, body.fields)
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, "pipeline": pipeline_payload(access)}


@router.put("/{item_id}/concepts", dependencies=[auth.EDIT])
def set_concepts(item_id: str, body: ConceptsBody, access: auth.Access = auth.VIEW) -> dict:
    """Replace an item's concept tags by hand."""
    try:
        result = bank_edit.set_concepts(
            access.ws, item_id, body.concepts, body.primary_concept
        )
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, "pipeline": pipeline_payload(access)}


@router.delete("/{item_id}", dependencies=[auth.EDIT])
def delete(item_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Remove one item from the bank."""
    try:
        result = bank_edit.delete_item(access.ws, item_id)
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, "pipeline": pipeline_payload(access)}
