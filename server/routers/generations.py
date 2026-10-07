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
"""

from fastapi import APIRouter, HTTPException, Query

from .. import auth
from .. import generations as store
from ..db.models import VIEWER
from ..editors import bank_edit
from ..editors.bank_edit import BankError
from .pipeline import pipeline_payload

router = APIRouter(prefix="/api/generations", tags=["generations"], dependencies=[auth.VIEW])

# What the detail adds to a row: how the exercise was made, beyond what was asked.
_PROVENANCE_KEYS = ("resolved", "inputs", "settings", "system_version", "prompt")


@router.get("")
def listing(
    concept: str | None = None,
    item_type: str | None = None,
    q: str | None = None,
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    access: auth.Access = auth.VIEW,
) -> dict:
    """Answer one page of your own stored exercises.

    `total` is what the filters match over everything you have generated here; there is no
    count of the instance's, which would report how much other people have produced.
    """
    records, total = store.list_for(
        access.ws,
        access.user.id,
        concept=concept,
        item_type=item_type,
        query=q,
        limit=limit,
        offset=offset,
    )
    return {
        "generations": [row_view(record, access.user) for record in records],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{generation_id}")
def detail(generation_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Answer one stored exercise, with the model's deliberation and how it was made."""
    record = _require(generation_id, access)
    output = record.get("output") or {}
    provenance = {key: record.get(key) for key in _PROVENANCE_KEYS}
    return {
        "generation": {
            **row_view(record, access.user),
            "thinking": output.get("thinking"),
            "retried": output.get("retried"),
            "format": record.get("format"),
            "provenance": without_bank(provenance) if access.role == VIEWER else provenance,
        },
    }


@router.post("/{generation_id}/promote", dependencies=[auth.EDIT])
def promote(generation_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Copy this exercise into the exemplars bank."""
    record = _require(generation_id, access)
    promoted = record.get("promoted_item_id")
    if promoted and bank_edit.has_item(access.ws, promoted):
        raise HTTPException(409, f"Este ejercicio ya está en el banco como «{promoted}».")
    try:
        result = bank_edit.add_item(
            access.ws,
            dict(store.item_of(record)),
            store.item_type_of(record) or None,
            store.concepts_of(record),
        )
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    store.mark_promoted(access.ws, access.user.id, record, result["item"]["id"])
    return {
        "generation": generation_id,
        "item": result["item"],
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


def row_view(record: dict, user) -> dict:
    """Render one stored exercise with its commission and the item itself.

    `concepts` is what was ASKED for, which is what «Generar más como este» reopens;
    `targets` is what ran — the bank's most frequent concepts when nothing was asked.
    `think` is the commission's too, a level or a bool. The author is the account asking
    on these routes; on the administrator's it is whoever wrote it, and None for an exercise
    whose account no longer exists.
    """
    commission = record.get("commission") or {}
    resolved = record.get("resolved") or {}
    job = record.get("job") or {}
    curriculum = resolved.get("curriculum")
    return {
        "id": record.get("id"),
        "created_at": store.created_at(record),
        "job_id": job.get("id"),
        "item_type": store.item_type_of(record),
        "concepts": list(commission.get("concepts") or []),
        "targets": store.concepts_of(record),
        "curriculum": list(curriculum if isinstance(curriculum, list) else []),
        "fixed": dict(commission.get("fixed") or {}),
        "omit": list(commission.get("omit") or []),
        "instructions": commission.get("instructions") or "",
        "think": commission.get("think", True),
        "effort": resolved.get("effort"),
        # Null for every exercise written before a commission could choose its model: the
        # screen says nothing rather than naming today's default, which did not write it.
        "model": resolved.get("model") or None,
        "author": {
            "id": getattr(user, "id", None),
            "name": getattr(user, "name", None),
            "username": getattr(user, "username", None),
        },
        "promoted_item_id": record.get("promoted_item_id"),
        "item": store.item_of(record),
        "checks": (record.get("output") or {}).get("checks"),
    }


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
