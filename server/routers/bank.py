from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..editors import bank_edit
from ..editors.bank_edit import BankError
from .pipeline import get_pipeline

router = APIRouter(prefix="/api/bank", tags=["bank"])


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
    order: str = Query("suspicion", pattern="^(suspicion|id)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> dict:
    try:
        return bank_edit.listing(
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
def coverage() -> dict:
    try:
        return bank_edit.coverage()
    except BankError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch("/{item_id}")
def patch(item_id: str, body: PatchBody) -> dict:
    try:
        result = bank_edit.patch_item(item_id, body.fields)
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, "pipeline": get_pipeline()}


@router.put("/{item_id}/concepts")
def set_concepts(item_id: str, body: ConceptsBody) -> dict:
    try:
        result = bank_edit.set_concepts(item_id, body.concepts, body.primary_concept)
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, "pipeline": get_pipeline()}


@router.delete("/{item_id}")
def delete(item_id: str) -> dict:
    try:
        result = bank_edit.delete_item(item_id)
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, "pipeline": get_pipeline()}
