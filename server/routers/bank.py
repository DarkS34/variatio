"""The exemplars bank: the items an instance learns its shapes from.

Declares `auth.EDIT` for the whole router, reads included: the bank's exercises carry their
solutions, and a student of the subject (`viewer`) reads none of them here — not the items,
not the coverage. What a teacher shows the class is read through `/api/exercises`, cut to it.
Each write answers with the chain's new state, so a screen never has to ask for it
separately.

A teacher adds an exercise by hand (`POST /api/bank`) and may have the system tag it in the
same press: the route queues `tag_item` on it, a job of its author's that runs in the
queue's second class, since somebody watches the concepts arrive.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from variatio.core import inference

from .. import auth, bank_marks, groups, singletons
from ..db.models import User
from ..editors import bank_edit
from ..editors.bank_edit import BankError
from ..jobs.catalogue import TAG_ITEM
from .jobs import gate_error
from .pipeline import pipeline_payload

router = APIRouter(prefix="/api/bank", tags=["bank"], dependencies=[auth.EDIT])


class PatchBody(BaseModel):
    """The subset of an item's fields being rewritten."""

    fields: dict


class ConceptsBody(BaseModel):
    """An item's concept tags, with which of them the item is actually about."""

    concepts: list[str]
    primary_concept: str | None = None


class Shown(BaseModel):
    """What the class sees of an exercise: nothing, all of it, or the fields chosen.

    `groups` names the groups of the class that see it; absent, the whole class does.
    """

    level: Literal["hidden", "full", "fields"] = "hidden"
    fields: list[str] = []
    groups: list[int] | None = None


class AddBody(BaseModel):
    """An exercise a teacher writes, and who decides its concepts: the system or the teacher.

    `set_aside` names an exercise a re-extraction put aside, corrected and brought back: it
    keeps where it came from, who added it and when. `visibility` is what the class sees of
    it from the start; hidden, like every exercise, when it says nothing.
    """

    item_type: str | None = None
    fields: dict
    tag: Literal["auto", "manual"] = "manual"
    concepts: list[str] = []
    primary_concept: str | None = None
    set_aside: str | None = None
    visibility: Shown | None = None


class VisibilityBody(Shown):
    """Who sees these exercises: nobody, everything of them, or the fields chosen.

    `fields` names fields across types: each exercise shows the ones its own type declares.
    """

    items: list[str]


class TagBody(BaseModel):
    """The exercises to tag again."""

    items: list[str]


@router.get("")
def listing(
    concept: str | None = None,
    untagged: bool | None = None,
    q: str | None = None,
    source: str | None = None,
    item_type: str | None = None,
    difficulty: str | None = None,
    order: str = Query("id", pattern="^(suspicion|difficulty|id|recent)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    origin: Literal["extracted", "manual", "generated"] | None = None,
    visible: bool = False,
    favourite: bool = False,
    access: auth.Access = auth.EDIT,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Answer one page of the bank, filtered and ordered as asked.

    A modality the profile does not declare is a 422 naming it, never an empty page: the
    filter is an equality, so an unknown value would read as "the bank has none of these"
    rather than "that does not exist". The 404 of this route means "there is no bank yet".
    A rung the profile does not declare is refused the same way and for the same reason.
    """
    try:
        result = bank_edit.listing(
            access.ws,
            concept=concept,
            untagged=untagged,
            query=q,
            source=source,
            item_type=item_type,
            difficulty=difficulty,
            order=order,
            page=page,
            page_size=page_size,
            origin=origin,
            favourites=_stars(db, access),
            visible_only=visible,
            favourites_only=favourite,
        )
    except BankError as exc:
        raise HTTPException(404, str(exc)) from exc
    _name_who_added(db, result["items"])

    declared = [t["key"] for t in result["item_types"]]
    if item_type and item_type not in declared:
        raise HTTPException(
            422,
            f"El perfil de ejemplares no declara la modalidad «{item_type}»; "
            f"las que hay: {', '.join(declared) or 'ninguna'}",
        )
    rungs = [d["value"] for d in result["difficulties"]]
    if difficulty and difficulty not in rungs:
        raise HTTPException(
            422,
            f"El perfil de ejemplares no declara el nivel «{difficulty}»; "
            f"los que hay: {', '.join(rungs) or 'ninguno'}",
        )
    return result


def _stars(db: DbSession, access: auth.Access) -> frozenset[str]:
    """Return the asking teacher's stars in this subject; none without a database row."""
    workspace_id = getattr(getattr(access, "workspace", None), "id", None)
    if not isinstance(workspace_id, int) or not isinstance(db, DbSession):
        return frozenset()
    return bank_marks.favourites(db, workspace_id, access.user.id)


def _name_who_added(db: DbSession, items: list[dict]) -> None:
    """Replace each `added_by` id with the person it names, or None for an account gone."""
    ids = {item["added_by"] for item in items if isinstance(item.get("added_by"), int)}
    people = {
        user.id: {"id": user.id, "name": user.name, "username": user.username}
        for user in (db.scalars(select(User).where(User.id.in_(ids))) if ids else [])
    }
    for item in items:
        if "added_by" in item:
            item["added_by"] = people.get(item["added_by"])


@router.get("/coverage")
def coverage(access: auth.Access = auth.EDIT) -> dict:
    """Answer how much of the graph the bank's tags actually reach."""
    try:
        return bank_edit.coverage(access.ws)
    except BankError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("")
def add(body: AddBody, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Add an exercise written by hand, tagged by the teacher or queued for the tagger.

    Asking for the tagger is checked BEFORE anything is written: with the syllabus or the
    types open, or no engine, the exercise is not saved and the screen keeps the form, so its
    author can choose the concepts instead.
    """
    if body.tag == "auto":
        refuse_tagging(access)
    checked_groups(db, access, body.visibility)
    returning = bank_edit.aside(access.ws).get(body.set_aside) if body.set_aside else None
    if body.set_aside and returning is None:
        raise HTTPException(404, "Ese ejercicio ya no está apartado.")
    was = (returning or {}).get("item") or {}
    try:
        result = bank_edit.add_item(
            access.ws,
            body.fields,
            body.item_type,
            [] if body.tag == "auto" else body.concepts,
            None if body.tag == "auto" else body.primary_concept,
            origin=bank_edit.origin_of(returning["id"], was) if returning else bank_edit.MANUAL,
            added_by=was.get("added_by") if returning else access.user.id,
            added_at=was.get("added_at") if returning else None,
        )
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    if body.set_aside:
        bank_edit.take_aside(access.ws, body.set_aside)
    show(access, result["item"]["id"], body.visibility)
    job = queue_tagging(access, [result["item"]["id"]]) if body.tag == "auto" else None
    return {**result, "job": job, "pipeline": pipeline_payload(access)}


# Declared above `/{item_id}`: FastAPI matches in order.
@router.get("/set-aside")
def set_aside(access: auth.Access = auth.EDIT) -> dict:
    """Answer the exercises a re-extraction could not keep, for their teacher to bring back."""
    return {
        "items": [
            {"key": key, "id": entry.get("id"), "at": entry.get("at"), "item": entry.get("item") or {}}
            for key, entry in bank_edit.aside(access.ws).items()
        ]
    }


@router.delete("/set-aside/{key}")
def drop_set_aside(key: str, access: auth.Access = auth.EDIT) -> dict:
    """Let go of one exercise put aside, for good."""
    if bank_edit.take_aside(access.ws, key) is None:
        raise HTTPException(404, "Ese ejercicio ya no está apartado.")
    return {"deleted": key}


@router.put("/visibility")
def set_visibility(
    body: VisibilityBody, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)
) -> dict:
    """Decide who sees these exercises. Not content of the bank: its approval does not move."""
    checked_groups(db, access, body)
    keys = []
    for item_id in body.items:
        try:
            key = bank_edit.key_of(access.ws, item_id)
        except BankError as exc:
            raise HTTPException(404, str(exc)) from exc
        if key is None:
            raise HTTPException(404, f"El ejercicio '{item_id}' no está en el banco.")
        keys.append(key)
    bank_marks.set_visibility(access.ws, keys, body.level, body.fields, body.groups)
    return {"items": body.items, "level": body.level, "groups": body.groups}


@router.post("/tag")
def tag(body: TagBody, access: auth.Access = auth.EDIT) -> dict:
    """Queue the tagger on some exercises again, after a teacher corrected what they say."""
    if not body.items:
        raise HTTPException(422, "No hay ningún ejercicio que etiquetar.")
    missing = [item_id for item_id in body.items if not bank_edit.has_item(access.ws, item_id)]
    if missing:
        raise HTTPException(404, f"No están en el banco: {', '.join(missing)}")
    refuse_tagging(access)
    return {"job": queue_tagging(access, body.items)}


def show(access: auth.Access, item_id: str, visibility: Shown | None) -> None:
    """Let the class see an exercise just added, as its author chose; nothing to do if hidden.

    Public because passing a generated exercise in (`apps.generation`) chooses it too. The
    groups were checked before anything was written (`checked_groups`).
    """
    if visibility is None or visibility.level == bank_marks.HIDDEN:
        return
    key = bank_edit.key_of(access.ws, item_id)
    if key is not None:
        bank_marks.set_visibility(
            access.ws, [key], visibility.level, visibility.fields, visibility.groups
        )


def checked_groups(db: DbSession, access: auth.Access, visibility: Shown | None) -> None:
    """Refuse groups that are not this class's, or a choice of groups that names none.

    Public for the reason `show` is.
    """
    if visibility is None or visibility.groups is None or visibility.level == bank_marks.HIDDEN:
        return
    if not visibility.groups:
        raise HTTPException(422, "Elige al menos un grupo, o toda la clase.")
    known = {group.id for group in groups.all_of(db, access.workspace)}
    if any(group not in known for group in visibility.groups):
        raise HTTPException(404, "Ese grupo no existe en esta asignatura.")


def refuse_tagging(access: auth.Access) -> None:
    """Refuse a tagging the chain or the engine would make fail: the gates of `tag`.

    Public because passing a generated exercise into the bank (`apps.generation`) asks the
    same of the same tagger.
    """
    error = gate_error(access.ws, "tag")
    if error:
        raise HTTPException(409, error)
    if not inference.is_available():
        raise HTTPException(
            503,
            f"No hay conexión con el motor de inferencia '{inference.engine_name()}'. "
            "Elige tú los conceptos, o vuelve a intentarlo cuando esté en marcha.",
        )


def queue_tagging(access: auth.Access, items: list[str]) -> dict:
    """Queue `tag_item` on these exercises, as a job of the teacher who asked."""
    job = singletons.runner.submit(
        TAG_ITEM,
        {"items": items},
        workspace=access.ws.slug,
        user_id=access.user.id,
        user_name=access.user.name,
    )
    return {**job.to_dict(), "queue_position": singletons.runner.queue_position(job.id)}


@router.patch("/{item_id}")
def patch(
    item_id: str, body: PatchBody, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)
) -> dict:
    """Rewrite some of an item's fields, carrying its marks to its new statement."""
    try:
        before = bank_edit.key_of(access.ws, item_id)
        result = bank_edit.patch_item(access.ws, item_id, body.fields)
        after = bank_edit.key_of(access.ws, item_id)
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    workspace_id = getattr(access.workspace, "id", None)
    if before and after and before != after and isinstance(workspace_id, int):
        bank_marks.move(access.ws, db, workspace_id, before, after)
    return {**result, "pipeline": pipeline_payload(access)}


@router.put("/{item_id}/favourite")
def star(item_id: str, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Mark one exercise with this teacher's star."""
    return _star(item_id, access, db, True)


@router.delete("/{item_id}/favourite")
def unstar(item_id: str, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Take this teacher's star off one exercise."""
    return _star(item_id, access, db, False)


def _star(item_id: str, access: auth.Access, db: DbSession, on: bool) -> dict:
    """Mark or unmark one exercise, refusing one the bank does not hold."""
    try:
        key = bank_edit.key_of(access.ws, item_id)
    except BankError as exc:
        raise HTTPException(404, str(exc)) from exc
    if key is None:
        raise HTTPException(404, f"El ejercicio '{item_id}' no está en el banco.")
    bank_marks.set_favourite(db, access.workspace.id, access.user.id, key, on)
    db.commit()
    return {"item": item_id, "favourite": on}


@router.put("/{item_id}/concepts")
def set_concepts(item_id: str, body: ConceptsBody, access: auth.Access = auth.EDIT) -> dict:
    """Replace an item's concept tags by hand."""
    try:
        result = bank_edit.set_concepts(
            access.ws, item_id, body.concepts, body.primary_concept
        )
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, "pipeline": pipeline_payload(access)}


@router.delete("/{item_id}")
def delete(item_id: str, access: auth.Access = auth.EDIT) -> dict:
    """Remove one item from the bank."""
    try:
        result = bank_edit.delete_item(access.ws, item_id)
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, "pipeline": pipeline_payload(access)}
