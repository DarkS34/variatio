"""The exercises this account has generated, kept so they can be read back.

Declares `auth.VIEW` for the whole router, deleting one's own included; promoting into the
bank adds `auth.EDIT`.

Every validated item is a file (`server/generations.py`) carrying the commission that
produced it — concepts, curriculum, fixed fields, extra instructions, which model wrote it
and how much it deliberated — and what that commission resolved to, because a statement
without its parameters can be read but neither judged nor reproduced.

EVERY ROUTE IS SCOPED TO THE ACCOUNT THAT ASKS, and there is no second scope to flip: a
filter somebody can turn off is not privacy. The membership bounds the workspace and the
author bounds the files inside it — each account's exercises are a directory of their own —
so two accounts preparing one subject do not read each other's exercises. Neither the owner
nor the administrator is an exception HERE — `_require` answers 404 for an exercise that is
not yours, because "it exists but is not yours" is itself something this refuses to say. The
installation administrator reads every account's, read-only, through its own panel
(`GET /api/admin/workspaces/{slug}/generations`), never through these routes.

A STUDENT READS THEIR EXERCISE WHOLE, AND NOT THE BANK IT WAS MADE FROM: the accepted
attempt's prompt quotes the chosen exemplars with their solutions, and `resolved.few_shot`
their bodies, so neither reaches an account whose role in the subject is `viewer`. The file
keeps both, and the administrator reads them from the panel.

A TEACHER PASSES THEIR OWN INTO THE BANK (2026-10-14): each row says whether it is in the
bank now (`in_bank`, the bank's id while that exercise is still there) and whether this
account may pass it (`promotable`), and the listing filters by both. Passing one may correct
it first and may have the system tag it, as a teacher's own exercise is (`tag_item`).
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from server import auth
from server import generations as store
from server.db.models import EDITOR, VIEWER
from server.editors import bank_edit
from server.editors.bank_edit import BankError
from server.generations import row_view
from server.pipeline.view import pipeline_payload
from server.routers.bank import Shown, checked_groups, queue_tagging, refuse_tagging, show
from variatio.loaders import locale

router = APIRouter(prefix="/api/generations", tags=["generations"], dependencies=[auth.VIEW])

# What the detail adds to a row: how the exercise was made, beyond what was asked.
_PROVENANCE_KEYS = ("resolved", "inputs", "settings", "system_version", "prompt")


class PromoteBody(BaseModel):
    """How a generated exercise goes into the bank: as written or corrected, and who tags it.

    Every field is optional so a bare press keeps working as it did: the exercise as the model
    wrote it, with the concepts it was generated for. `concepts` absent means those.
    """

    fields: dict | None = None
    tag: Literal["auto", "manual"] = "manual"
    concepts: list[str] | None = None
    primary_concept: str | None = None
    visibility: Shown | None = None


@router.get("")
def listing(
    concept: str | None = None,
    item_type: str | None = None,
    q: str | None = None,
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    bank: Literal["in", "out"] | None = None,
    difficulty: str | None = None,
    access: auth.Access = auth.VIEW,
) -> dict:
    """Answer one page of your own stored exercises.

    `total` is what the filters match over everything you have generated here; there is no
    count of the instance's, which would report how much other people have produced. `bank`
    keeps the ones in the bank now or the ones out of it, a teacher's question: a student
    reads no bank, so it filters nothing for them.
    """
    teacher = auth.at_least(access, EDITOR)
    in_bank = bank_edit.item_ids(access.ws) if teacher else frozenset()
    level_field = locale.difficulty(access.ws)[0] if difficulty else None

    def keep(record: dict) -> bool:
        """Whether a record answers the bank's and the level's filters."""
        if level_field and store.item_of(record).get(level_field) != difficulty:
            return False
        if teacher and bank:
            return (_bank_id(record, in_bank) is not None) == (bank == "in")
        return True

    records, total = store.list_for(
        access.ws,
        access.user.id,
        concept=concept,
        item_type=item_type,
        query=q,
        limit=limit,
        offset=offset,
        keep=keep,
    )
    return {
        "generations": [
            _with_bank(row_view(record, access.user), record, in_bank, teacher)
            for record in records
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _with_bank(row: dict, record: dict, in_bank: frozenset[str], teacher: bool) -> dict:
    """Say whether the exercise is in the bank now and whether this account may pass it in."""
    bank_id = _bank_id(record, in_bank) if teacher else None
    return {**row, "in_bank": bank_id, "promotable": teacher and bank_id is None}


def _bank_id(record: dict, in_bank: frozenset[str]) -> str | None:
    """Return the bank's id of an exercise passed into it, while the bank still holds it."""
    promoted = record.get("promoted_item_id")
    return promoted if promoted and promoted in in_bank else None


@router.get("/{generation_id}")
def detail(generation_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Answer one stored exercise, with the model's deliberation and how it was made."""
    record = _require(generation_id, access)
    output = record.get("output") or {}
    provenance = {key: record.get(key) for key in _PROVENANCE_KEYS}
    teacher = auth.at_least(access, EDITOR)
    in_bank = bank_edit.item_ids(access.ws) if teacher else frozenset()
    return {
        "generation": {
            **_with_bank(row_view(record, access.user), record, in_bank, teacher),
            "thinking": output.get("thinking"),
            "retried": output.get("retried"),
            "format": record.get("format"),
            "provenance": without_bank(provenance) if access.role == VIEWER else provenance,
        },
    }


@router.post("/{generation_id}/promote", dependencies=[auth.EDIT])
def promote(
    generation_id: str,
    body: PromoteBody | None = None,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Pass this exercise into the exemplars bank, corrected or as the model wrote it.

    A correction lands in the bank and never in this file, which is the record of what the
    model wrote. A field the commission left out has to be written to pass it in: an exemplar
    carries every field of its type, and the bank's schema refuses one without it.
    """
    body = body or PromoteBody()
    record = _require(generation_id, access)
    promoted = record.get("promoted_item_id")
    if promoted and bank_edit.has_item(access.ws, promoted):
        raise HTTPException(409, f"Este ejercicio ya está en el banco como «{promoted}».")
    if body.tag == "auto":
        refuse_tagging(access)
    checked_groups(db, access, body.visibility)
    concepts = store.concepts_of(record) if body.concepts is None else body.concepts
    try:
        result = bank_edit.add_item(
            access.ws,
            dict(store.item_of(record) if body.fields is None else body.fields),
            store.item_type_of(record) or None,
            [] if body.tag == "auto" else concepts,
            None if body.tag == "auto" else body.primary_concept,
            origin=bank_edit.GENERATED,
            added_by=access.user.id,
        )
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    item_id = result["item"]["id"]
    store.mark_promoted(access.ws, access.user.id, record, item_id)
    show(access, item_id, body.visibility)
    job = queue_tagging(access, [item_id]) if body.tag == "auto" else None
    return {
        "generation": generation_id,
        "item": result["item"],
        "job": job,
        "pipeline": pipeline_payload(access),
    }


@router.delete("/{generation_id}")
def remove(generation_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Delete one of your own stored exercises.

    Any member may, a student included: `_require` refuses an exercise that is not yours,
    so nobody can delete somebody else's work whatever their role — the same door that
    hides it.
    """
    _require(generation_id, access)
    store.delete(access.ws, access.user.id, generation_id)
    return {"deleted": generation_id}


def _require(generation_id: str, access: auth.Access) -> dict:
    """Load one of YOUR exercises of this workspace, or 404.

    An exercise of another instance, of another account and a malformed id are all simply
    unknown: the 404 is the same sentence for the three, because a 403 would confirm that
    the id names something. Privacy is the directory read — your own — not a comparison.
    """
    record = store.get(access.ws, access.user.id, generation_id)
    if record is None:
        raise HTTPException(404, "Ese ejercicio no existe.")
    return record


def without_bank(provenance: dict) -> dict:
    """Return how an exercise was made, without the prompt and the exemplars' bodies.

    The exemplars stay listed by id and origin — which ones, never what they say.
    """
    resolved = provenance.get("resolved")
    if isinstance(resolved, dict) and isinstance(resolved.get("few_shot"), list):
        resolved = {
            **resolved,
            "few_shot": [
                {key: value for key, value in entry.items() if key != "item"}
                for entry in resolved["few_shot"]
                if isinstance(entry, dict)
            ],
        }
    return {**provenance, "resolved": resolved, "prompt": None}
