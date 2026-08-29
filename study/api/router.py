"""The blind comparison, over HTTP.

The blinding is imposed HERE and not in the browser. Any filtering done in React travels
in the bundle and, worse, the JSON has already reached the client: the only way for the
comparison to actually be blind is for the server never to send the mapping until the
evaluator has committed to a choice.

What this router deliberately does NOT serve is the study's aggregates and its CSV, which
are `/api/admin/evaluations`': handing an evaluator the running score of the thing they are
judging invites them to even it out, and a per-session export of everybody's judgements is
research data rather than a feature of the screen where you compare three cards.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from server import auth
from server import curriculum as curriculum_store
from server import runtime
from server.db.models import EvalSession
from server.editors import kg_edit
from server.routers.jobs import gate_error

from .. import ARM_LABELS, ARMS, EvaluationSession
from ..arms import external
from . import instruments, queries
from . import store as evaluation_store

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"], dependencies=[auth.VIEW])


class EvaluationBody(BaseModel):
    """A commission to compare. `force` runs it with the chain not yet approved."""

    concepts: list[str] = []
    item_type: str | None = None
    fixed: dict = {}
    curriculum: list[str] | None = None
    instructions: str | None = None
    seed: int | None = None
    force: bool = False


class ChoiceBody(BaseModel):
    """Which position won, or null for «ninguna», plus an optional note."""

    choice: int | None = None
    comment: str | None = None


class DeleteBody(BaseModel):
    """The sessions to remove."""

    ids: list[str]


class RatingBody(BaseModel):
    """The post-reveal rubric over the system's variant. Every field is optional."""

    originality: int | None = None
    complexity: int | None = None
    concept_fit: int | None = None
    soundness: int | None = None
    usability: str | None = None
    comment: str | None = None


class TriageBody(BaseModel):
    """One blind answer, addressed BY POSITION because that is what the evaluator saw."""

    position: int
    value: str


class DeclineBody(BaseModel):
    """An optional note beside «no tengo criterio para juzgar esto»."""

    comment: str | None = None


# LAUNCH ----------------------------------------------------------------------------------------


@router.post("", dependencies=[auth.EDIT])
def launch(body: EvaluationBody, access: auth.Access = auth.VIEW) -> dict:
    """Queue one blind comparison for this workspace."""
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


@router.get("")
def listing(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Return YOUR own sessions, your queue, and how this account is asked things.

    Not the workspace's sessions: a session is a judgement, and reading a colleague's
    before making your own is the one way a blind comparison stops being blind afterwards.
    """
    sessions, total = evaluation_store.listing(
        db, access.workspace.id, author=access.user.id, limit=limit, offset=offset
    )
    # The head of the chain, not the whole of it: this block is the "is the commercial arm
    # usable at all" banner, and which provider ends up answering is recorded per session.
    provider, model = external.primary()
    assigned = queries.assigned_to(db, access.workspace.id, access.user.id)
    return {
        "sessions": [_summary(header) for header in sessions],
        "total": total,
        "limit": limit,
        "offset": offset,
        "arms": [{"key": arm, "label": ARM_LABELS[arm]} for arm in ARMS],
        # The queue, which is what the screen opens on: what somebody handed this evaluator,
        # oldest first, pending ones ahead of the ones already judged.
        "queue": _queue(assigned),
        # Served rather than hard-coded in the browser because it IS the instrument.
        "instruments": instruments.for_profile(access.user.evaluator_profile),
        "external": {
            "provider": provider,
            "model": model,
            "configured": external.is_configured(),
            "reason": external.unavailable_reason(),
        },
    }


def _queue(rows: list) -> dict:
    """Shape what this evaluator was handed: pending first, oldest first inside each half.

    A queue is worked from the front, so «la siguiente» has to mean the same thing on every
    reload. Who assigned each session is recorded and read by the panel, and deliberately
    absent here: on the evaluator's own screen it invites reading the judgement as owed to
    a person rather than to the study.
    """
    pending = [row for row in rows if row.chosen_at is None and row.declined_at is None]
    done = [row for row in rows if row.chosen_at is not None or row.declined_at is not None]
    return {
        "total": len(rows),
        "pending": len(pending),
        "items": [
            {
                "id": row.id,
                "created_at": row.created_at.timestamp() if row.created_at else 0.0,
                "concepts": list(row.concepts or []),
                "item_type": row.item_type or "",
                "instructions": row.instructions or "",
                "decided": row.chosen_at is not None,
                "declined": row.declined_at is not None,
                "rated": bool(row.rating),
            }
            for row in [*pending, *done]
        ],
    }


# ONE SESSION -----------------------------------------------------------------------------------
#
# Every fixed path stays ABOVE the `/{session_id}` wildcards below. FastAPI matches in
# declaration order, so one added underneath is swallowed and answers a plausible 404 from
# a route nobody meant to call. `tests/study/test_route_order.py` pins it.


@router.delete("", dependencies=[auth.EDIT])
def delete_sessions(
    body: DeleteBody, access: auth.Access = auth.VIEW, db: DbSession = Depends(auth.db)
) -> dict:
    """Delete sessions of your own, refusing any that is not."""
    ids = list(dict.fromkeys(i for i in body.ids if i))
    if not ids:
        raise HTTPException(422, "No se ha indicado ninguna sesión.")
    owned = [_require(db, session_id, access).id for session_id in ids]
    deleted = queries.delete_evaluations(db, owned)
    return {"deleted": deleted}


@router.get("/{session_id}")
def detail(
    session_id: str, access: auth.Access = auth.VIEW, db: DbSession = Depends(auth.db)
) -> dict:
    """Return one session, blind or revealed, and start its clock the first time.

    Time-on-task is measured from `opened_at`, which is written once and never moved: a
    reload must not restart it. The evaluator never sees it.
    """
    row = _require(db, session_id, access)
    if row.user_id == access.user.id and row.chosen_at is None and row.declined_at is None:
        evaluation_store.mark_opened(db, row)
        db.refresh(row)
    return _payload(EvaluationSession.from_dict(row.trace))


@router.post("/{session_id}/triage", dependencies=[auth.EDIT])
def triage(
    session_id: str,
    body: TriageBody,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Record one blind per-card answer.

    It has to arrive before the choice, which is the entire reason it exists: a score given
    after the reveal is a score about a name.
    """
    row = _require(db, session_id, access)
    try:
        session = evaluation_store.record_triage(db, row, body.position, body.value)
    except ValueError as e:
        if str(e) == "already-chosen":
            raise HTTPException(409, "Esta sesión ya está cerrada.") from None
        raise HTTPException(422, str(e)) from None
    return _payload(session)


@router.post("/{session_id}/decline", dependencies=[auth.EDIT])
def decline(
    session_id: str,
    body: DeclineBody,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Close the session without a preference.

    With evaluators drawn from different subjects this is a real answer and not an escape
    hatch. It sets `declined_at` and never `chosen_at`, so it enters no preference count.
    """
    row = _require(db, session_id, access)
    try:
        session = evaluation_store.record_decline(db, row, body.comment)
    except ValueError as e:
        if str(e) == "already-chosen":
            raise HTTPException(409, "Esta sesión ya está cerrada.") from None
        raise HTTPException(422, str(e)) from None
    return _payload(session)


@router.post("/{session_id}/choice", dependencies=[auth.EDIT])
def choose(
    session_id: str,
    body: ChoiceBody,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Record the forced choice, which is what reveals the session.

    A session is judged once: letting it be re-chosen after the reveal would make the datum
    something other than blind.
    """
    row = _require(db, session_id, access)
    try:
        session = evaluation_store.record_choice(db, row, body.choice, body.comment)
    except ValueError as e:
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
    """Record the post-reveal rubric, which is refused until a choice exists."""
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


def _require(db: DbSession, session_id: str, access: auth.Access) -> EvalSession:
    """Return the session only when it is this workspace's AND this account's own.

    The ownership half is an EQUALITY and not «not mine and not an administrator»: the
    looser form let an administrator answer somebody else's session, recorded under that
    somebody because no answer rewrites `user_id`, and let unassigned stock through for
    everyone. Reading another account's session is the panel's own route, which never
    writes.
    """
    row = queries.get_evaluation(db, session_id)
    if row is None or row.workspace_id != access.workspace.id:
        raise HTTPException(404, f"No existe la sesión '{session_id}'")
    if row.user_id != access.user.id:
        raise HTTPException(404, f"No existe la sesión '{session_id}'")
    return row


def _summary(header: dict) -> dict:
    """Shape one row of the listing, withholding the per-arm history until it is judged.

    A pending session that admits «the commercial one was unavailable» hands over the
    identity of whichever card shows no exercise.
    """
    decided = bool(header.get("chosen_at"))
    statuses = header.get("arm_status") or {}
    return {
        "id": header["id"],
        "created_at": header.get("created_at"),
        "concepts": header.get("concepts") or [],
        "item_type": header.get("item_type"),
        "instructions": header.get("instructions") or "",
        "assigned": bool(header.get("assigned")),
        "choice": header.get("choice"),
        "choice_arm": header.get("choice_arm"),
        "chosen_at": header.get("chosen_at"),
        "declined_at": header.get("declined_at"),
        "rated": bool(header.get("rating")),
        "think": bool(header.get("think", True)) if decided else None,
        "arm_status": statuses if decided else {},
        "without_item": sum(1 for status in statuses.values() if status != "ok"),
    }


def _payload(session: EvaluationSession) -> dict:
    """Render one session, revealing the mapping only once it is finished.

    A declined session reveals too: it is over, nobody will judge it, and withholding the
    answer from someone who just said they could not judge it punishes them for saying so.
    """
    revealed = session.finished
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
            "assigned": session.assigned_by is not None,
            "triage": dict(session.triage),
            "choice": session.choice,
            "choice_arm": session.choice_arm,
            "chosen_at": session.chosen_at,
            "declined_at": session.declined_at,
            "evaluator_note": session.evaluator_note,
            "rating": session.rating,
            # The seed IS the shuffle. `think` identifies no card, being the same for the
            # three, but it colours the reading, and the point of drawing it was to measure
            # it rather than to have it judged with that in mind.
            "seed": session.seed if revealed else None,
            "think": session.think if revealed else None,
        },
        "positions": [_position(session, index + 1, revealed) for index in range(len(ARMS))],
    }


def _position(session: EvaluationSession, position: int, revealed: bool) -> dict:
    """Render one card: the item alone while blind, the whole trace once revealed.

    `failed` and `unavailable` collapse into one neutral status before the reveal, because
    saying a proposal is unavailable for a spent quota identifies the commercial arm before
    a single card has been read.
    """
    result = session.arms[session.arm_at(position)]

    if not revealed:
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
        "checks": result.checks,
        "retried": result.retried,
    }
