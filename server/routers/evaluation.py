"""The blind comparison, over HTTP.

The blinding is imposed HERE and not in the browser. Any filtering done in React travels
in the bundle and, worse, the JSON has already reached the client: the only way for the
comparison to actually be blind is for the server never to send the mapping until the
evaluator has committed to a choice.
"""

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from variant_generator import config
from variant_generator.evaluation import ARM_LABELS, ARMS, EvaluationSession
from variant_generator.evaluation import external

from .. import auth, evaluation_store, runtime
from .jobs import gate_error

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"], dependencies=[auth.VIEW])


class EvaluationBody(BaseModel):
    concepts: list[str] = []
    item_type: str | None = None
    fixed: dict = {}
    curriculum: list[str] = []
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
def launch(body: EvaluationBody) -> dict:
    if not body.concepts:
        raise HTTPException(422, "Hay que elegir al menos un concepto objetivo.")
    if not body.force:
        error = gate_error("evaluate")
        if error:
            raise HTTPException(409, error)

    # No `n`: one item per arm per session is what makes the session the statistical unit.
    params = {
        "concepts": body.concepts,
        "item_type": body.item_type,
        "fixed": body.fixed,
        "curriculum": body.curriculum,
        "instructions": body.instructions,
        "seed": body.seed,
    }
    job = runtime.runner.submit("evaluate", params)
    return {"job": job.to_dict(), "since": runtime.bus.last_seq}


# LISTING ---------------------------------------------------------------------------------------


@router.get("/export.csv")
def export() -> Response:
    return Response(
        content=evaluation_store.export_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="evaluation_sessions.csv"'},
    )


@router.get("")
def listing(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)
) -> dict:
    sessions, total = evaluation_store.listing(limit=limit, offset=offset)
    return {
        "sessions": [_summary(header) for header in sessions],
        "total": total,
        "limit": limit,
        "offset": offset,
        "aggregates": evaluation_store.aggregates(),
        "arms": [{"key": arm, "label": ARM_LABELS[arm]} for arm in ARMS],
        "external": {
            "provider": config.EVAL_EXTERNAL_PROVIDER,
            "model": config.EVAL_EXTERNAL_MODEL_ID,
            "configured": external.is_configured(),
            "reason": external.unavailable_reason(),
        },
    }


# ONE SESSION -----------------------------------------------------------------------------------


@router.get("/{session_id}")
def detail(session_id: str) -> dict:
    return _payload(_require(session_id))


@router.post("/{session_id}/choice", dependencies=[auth.EDIT])
def choose(session_id: str, body: ChoiceBody) -> dict:
    _require(session_id)
    try:
        session = evaluation_store.record_choice(session_id, body.choice, body.comment)
    except KeyError:
        raise HTTPException(404, f"No existe la sesión '{session_id}'") from None
    except ValueError as e:
        # A session is judged once: letting it be re-chosen after the reveal would make
        # the datum something other than blind.
        if str(e) == "already-chosen":
            raise HTTPException(409, "Esta sesión ya tenía una elección registrada.") from None
        raise HTTPException(422, str(e)) from None
    return _payload(session)


@router.post("/{session_id}/rating", dependencies=[auth.EDIT])
def rate(session_id: str, body: RatingBody) -> dict:
    _require(session_id)
    try:
        session = evaluation_store.record_rating(
            session_id, {**body.model_dump(exclude_none=True), "arm": "system"}
        )
    except KeyError:
        raise HTTPException(404, f"No existe la sesión '{session_id}'") from None
    except ValueError as e:
        if str(e) == "not-chosen-yet":
            raise HTTPException(
                409, "La rúbrica se rellena después de elegir, no antes."
            ) from None
        raise HTTPException(422, str(e)) from None
    return _payload(session)


# SHAPING ---------------------------------------------------------------------------------------


def _require(session_id: str) -> EvaluationSession:
    session = evaluation_store.load(session_id)
    if session is None:
        raise HTTPException(404, f"No existe la sesión '{session_id}'")
    return session


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
            # Only after the reveal: the seed is the shuffle.
            "seed": session.seed if revealed else None,
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
