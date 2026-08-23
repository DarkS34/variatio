"""The blind comparison, over HTTP.

The blinding is imposed HERE and not in the browser. Any filtering done in React travels
in the bundle and, worse, the JSON has already reached the client: the only way for the
comparison to actually be blind is for the server never to send the mapping until the
evaluator has committed to a choice.

What this router deliberately no longer serves, as of phase 3: the study's aggregates and
its CSV. Both moved to `/api/admin/evaluations`. Handing an evaluator the running score of
the thing they are judging invites them to even it out, and a per-session export of
everybody's judgements is research data, not a feature of the screen where you compare
three cards.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from study import ARM_LABELS, ARMS, EvaluationSession
from study.arms import external

from .. import auth
from .. import curriculum as curriculum_store
from .. import evaluation_store, runtime
from ..db import study
from ..db.models import EvalSession
from ..editors import kg_edit
from .jobs import gate_error

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"], dependencies=[auth.VIEW])


class EvaluationBody(BaseModel):
    concepts: list[str] = []
    item_type: str | None = None
    fixed: dict = {}
    curriculum: list[str] | None = None
    instructions: str | None = None
    seed: int | None = None
    force: bool = False


class ChoiceBody(BaseModel):
    choice: int | None = None
    comment: str | None = None


class RatingBody(BaseModel):
    originality: int | None = None
    complexity: int | None = None
    concept_fit: int | None = None
    soundness: int | None = None
    usability: str | None = None
    comment: str | None = None


# LAUNCH ----------------------------------------------------------------------------------------


@router.post("", dependencies=[auth.EDIT])
def launch(body: EvaluationBody, access: auth.Access = auth.VIEW) -> dict:
    if not body.concepts:
        raise HTTPException(422, "Hay que elegir al menos un concepto objetivo.")
    if not body.force:
        error = gate_error(access.ws, "evaluate")
        if error:
            raise HTTPException(409, error)

    graph = kg_edit.load_graph(access.ws)
    curriculum = curriculum_store.resolve(access.ws, graph, body.curriculum)

    # No `n`: one item per arm per session is what makes the session the statistical unit.
    params = {
        "concepts": body.concepts,
        "item_type": body.item_type,
        "fixed": body.fixed,
        "curriculum": curriculum or [],
        "instructions": body.instructions,
        "seed": body.seed,
    }
    job = runtime.runner.submit(
        "evaluate",
        params,
        workspace=access.ws.slug,
        user_id=access.user.id,
        user_name=access.user.name,
    )
    return {"job": job.to_dict(), "since": runtime.bus.last_seq}


# LISTING ---------------------------------------------------------------------------------------


# Your own sessions, so you can reopen one you left undecided. Not the workspace's: a
# session is a judgement, and reading a colleague's before making your own is the one way
# a blind comparison stops being blind after the fact.
@router.get("")
def listing(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    sessions, total = evaluation_store.listing(
        db, access.workspace.id, author=access.user.id, limit=limit, offset=offset
    )
    # The head of the chain, not the whole of it: this block is the "is the commercial arm
    # usable at all" banner, and which provider ends up answering is recorded per session.
    provider, model = external.primary()
    return {
        "sessions": [_summary(header) for header in sessions],
        "total": total,
        "limit": limit,
        "offset": offset,
        "arms": [{"key": arm, "label": ARM_LABELS[arm]} for arm in ARMS],
        "external": {
            "provider": provider,
            "model": model,
            "configured": external.is_configured(),
            "reason": external.unavailable_reason(),
        },
    }


# ONE SESSION -----------------------------------------------------------------------------------


@router.get("/{session_id}")
def detail(
    session_id: str, access: auth.Access = auth.VIEW, db: DbSession = Depends(auth.db)
) -> dict:
    row = _require(db, session_id, access)
    return _payload(EvaluationSession.from_dict(row.trace))


@router.post("/{session_id}/choice", dependencies=[auth.EDIT])
def choose(
    session_id: str,
    body: ChoiceBody,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    row = _require(db, session_id, access)
    try:
        session = evaluation_store.record_choice(db, row, body.choice, body.comment)
    except ValueError as e:
        # A session is judged once: letting it be re-chosen after the reveal would make
        # the datum something other than blind.
        if str(e) == "already-chosen":
            raise HTTPException(409, "Esta sesión ya tenía una elección registrada.") from None
        raise HTTPException(422, str(e)) from None
    return _payload(session)


@router.post("/{session_id}/rating", dependencies=[auth.EDIT])
def rate(
    session_id: str,
    body: RatingBody,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    row = _require(db, session_id, access)
    try:
        session = evaluation_store.record_rating(
            db, row, {**body.model_dump(exclude_none=True), "arm": "system"}
        )
    except ValueError as e:
        if str(e) == "not-chosen-yet":
            raise HTTPException(
                409, "La rúbrica se rellena después de elegir, no antes."
            ) from None
        raise HTTPException(422, str(e)) from None
    return _payload(session)


# SHAPING ---------------------------------------------------------------------------------------


# Two conditions, not one: the session has to belong to this workspace *and* to whoever is
# asking. The workspace check alone would let a colleague open a comparison they never ran
# and read its reveal.
def _require(db: DbSession, session_id: str, access: auth.Access) -> EvalSession:
    row = study.get_evaluation(db, session_id)
    if row is None or row.workspace_id != access.workspace.id:
        raise HTTPException(404, f"No existe la sesión '{session_id}'")
    if row.user_id is not None and row.user_id != access.user.id and not access.user.is_admin:
        raise HTTPException(404, f"No existe la sesión '{session_id}'")
    return row


def _summary(header: dict) -> dict:
    decided = bool(header.get("chosen_at"))
    statuses = header.get("arm_status") or {}
    return {
        "id": header["id"],
        "created_at": header.get("created_at"),
        "concepts": header.get("concepts") or [],
        "item_type": header.get("item_type"),
        "instructions": header.get("instructions") or "",
        "choice": header.get("choice"),
        "choice_arm": header.get("choice_arm"),
        "chosen_at": header.get("chosen_at"),
        "rated": bool(header.get("rating")),
        # Like `arm_status`: history of a judged session, withheld while it is pending.
        "think": bool(header.get("think", True)) if decided else None,
        # Per-arm outcomes are history, and history only exists once the session has been
        # judged: a pending session that admits "the commercial one was unavailable" hands
        # over the identity of whichever card shows no exercise.
        "arm_status": statuses if decided else {},
        "without_item": sum(1 for status in statuses.values() if status != "ok"),
    }


def _payload(session: EvaluationSession) -> dict:
    revealed = session.decided
    return {
        "session": {
            "id": session.id,
            "created_at": session.created_at,
            "job_id": session.job_id,
            "concepts": session.concepts,
            "item_type": session.item_type,
            "fixed": session.fixed,
            "curriculum": session.curriculum,
            "instructions": session.instructions,
            "revealed": revealed,
            "choice": session.choice,
            "choice_arm": session.choice_arm,
            "chosen_at": session.chosen_at,
            "evaluator_note": session.evaluator_note,
            "rating": session.rating,
            # Only after the reveal: the seed is the shuffle, and the reasoning mode is
            # the same for the three cards, so telling it beforehand identifies none of
            # them — but it does colour the reading of what is on screen, and the point of
            # drawing it was to measure it, not to have it judged with that in mind.
            "seed": session.seed if revealed else None,
            "think": session.think if revealed else None,
        },
        "positions": [_position(session, index + 1, revealed) for index in range(len(ARMS))],
    }


def _position(session: EvaluationSession, position: int, revealed: bool) -> dict:
    result = session.arms[session.arm_at(position)]

    if not revealed:
        # `failed` and `unavailable` collapse into one neutral status on purpose: telling
        # the evaluator that a proposal is unavailable because a quota ran out identifies
        # the commercial arm before a single card has been read.
        return {
            "position": position,
            "status": "ok" if result.status == "ok" else "no_item",
            "item": result.item,
        }

    return {
        "position": position,
        "status": result.status,
        "item": result.item,
        "arm": result.arm,
        "arm_label": ARM_LABELS[result.arm],
        "model": result.model,
        "provider": result.provider,
        "prompt": result.prompt,
        "raw_response": result.raw_response,
        "exemplar_ids": result.exemplar_ids,
        "elapsed_ms": result.elapsed_ms,
        "error": result.error,
    }
