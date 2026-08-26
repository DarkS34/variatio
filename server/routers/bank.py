from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .. import auth
from ..editors import bank_edit
from ..editors.bank_edit import BankError
from .pipeline import pipeline_payload

router = APIRouter(prefix="/api/bank", tags=["bank"], dependencies=[auth.VIEW])


class PatchBody(BaseModel):
    fields: dict


class ConceptsBody(BaseModel):
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
    try:
        return bank_edit.listing(
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


@router.get("/coverage")
def coverage(access: auth.Access = auth.VIEW) -> dict:
    try:
        return bank_edit.coverage(access.ws)
    except BankError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch("/{item_id}", dependencies=[auth.EDIT])
def patch(item_id: str, body: PatchBody, access: auth.Access = auth.VIEW) -> dict:
    try:
        result = bank_edit.patch_item(access.ws, item_id, body.fields)
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, "pipeline": pipeline_payload(access)}


@router.put("/{item_id}/concepts", dependencies=[auth.EDIT])
def set_concepts(item_id: str, body: ConceptsBody, access: auth.Access = auth.VIEW) -> dict:
    try:
        result = bank_edit.set_concepts(
            access.ws, item_id, body.concepts, body.primary_concept
        )
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, "pipeline": pipeline_payload(access)}


@router.delete("/{item_id}", dependencies=[auth.EDIT])
def delete(item_id: str, access: auth.Access = auth.VIEW) -> dict:
    try:
        result = bank_edit.delete_item(access.ws, item_id)
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, "pipeline": pipeline_payload(access)}
