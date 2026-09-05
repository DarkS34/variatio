"""What a teacher answered about each artifact, over HTTP.

One router rather than a couple of routes bolted onto `routers/pipeline.py`, and it lives
in `evaluation/` for the reason the register gives: this is a measurement of the system, and a
system that contains its own measurement cannot be handed over without it. The screens
that draw it are stage screens; what they are collecting is research data.

THE HASH IS NEVER TAKEN FROM THE REQUEST. Which build was judged is the one fact that
makes a row a measurement, so it is resolved here from the file on disk — the same digest
`ReviewState.state` reports and approvals record. A client that sent its own would be
stamping a verdict onto whatever it happened to believe was built.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from server import auth, review, runtime

from . import stage_instruments, stage_queries

router = APIRouter(
    prefix="/api/stage-evaluations", tags=["stage-evaluations"], dependencies=[auth.VIEW]
)


class AnswersBody(BaseModel):
    """One filled-in form. Every field is optional: a half-answered form is still a datum."""

    answers: dict = {}
    overall: int | None = None
    note: str | None = None
    job_id: str | None = None
    # Whether this person had corrected the artifact by hand before answering. Absent is
    # «no se sabe» and never «no»: a client that does not send it is not denying it, and
    # `stage_queries.save` refuses to let an absence lower what a row already records.
    curated: bool | None = None


def _artifact(artifact: str) -> str:
    """Refuse anything that is not one of the three stages of the chain."""
    if artifact not in review.ARTIFACTS:
        raise HTTPException(404, f"No existe la etapa «{artifact}».")
    return artifact


def _digest(access: auth.Access, artifact: str) -> str | None:
    """The digest of what is on disk right now, or None when nothing is built."""
    return runtime.review_state(access.ws).state(artifact)["hash"]


def _mine(row) -> dict | None:
    """One person's own row as the form reads it back."""
    if row is None:
        return None
    return {
        "answers": row.answers or {},
        "overall": row.overall,
        "note": row.note,
        # Passed through as it stands, `null` included: «nadie lo dijo» is a third state
        # and the form has to be able to tell it from a «no», so it is never folded to one.
        "curated": row.curated,
        # «Contestada» is `overall`, which is the one question asked of all three stages
        # and the last one on the form: with it set, the person reached the end.
        "answered": row.overall is not None,
        "instrument": row.instrument,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _payload(artifact: str, digest: str | None, row) -> dict:
    """What both the read and the save answer: the questions, and this person's answers.

    One function because the client treats a save's reply as the form's new state, so the
    two shapes have to be the same one or a save blanks the screen.
    """
    return {
        "artifact": artifact,
        # Nothing to judge until something is built, and the screen has to be able to say
        # so rather than draw a form about a file that does not exist.
        "built": digest is not None,
        "hash": digest,
        "instrument": stage_instruments.for_artifact(artifact),
        "mine": _mine(row),
    }


@router.get("/{artifact}")
def read(
    artifact: str,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """The questions for this stage, plus whatever this person already answered about it."""
    artifact = _artifact(artifact)
    digest = _digest(access, artifact)
    row = (
        stage_queries.mine(db, access.workspace.id, access.user.id, artifact, digest)
        if digest
        else None
    )
    return _payload(artifact, digest, row)


@router.post("/{artifact}/opened", dependencies=[auth.EDIT])
def opened(
    artifact: str,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Record that the form reached this person, once, without moving an earlier stamp.

    A POST and not a side effect of the GET: a read that writes is a read nobody can cache
    or retry, and the client knows something the server cannot — that the form was actually
    drawn, rather than the payload merely fetched.
    """
    artifact = _artifact(artifact)
    digest = _digest(access, artifact)
    if digest is None:
        raise HTTPException(409, "Todavía no hay nada construido que valorar.")
    row = stage_queries.mark_opened(db, access.workspace.id, access.user.id, artifact, digest)
    return {"opened_at": row.opened_at}


@router.put("/{artifact}", dependencies=[auth.EDIT])
def write(
    artifact: str,
    body: AnswersBody,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Save this person's verdict on the build that is on disk right now."""
    artifact = _artifact(artifact)
    digest = _digest(access, artifact)
    if digest is None:
        raise HTTPException(409, "Todavía no hay nada construido que valorar.")

    overall = body.overall
    if overall is not None and not (
        stage_instruments.OVERALL_MIN <= overall <= stage_instruments.OVERALL_MAX
    ):
        raise HTTPException(
            422,
            f"La valoración de conjunto va de {stage_instruments.OVERALL_MIN} "
            f"a {stage_instruments.OVERALL_MAX}.",
        )

    row = stage_queries.save(
        db,
        access.workspace.id,
        access.user.id,
        artifact,
        digest,
        instrument=stage_instruments.VERSION,
        # Checked against what this artifact actually asks, never stored as it arrived.
        answers=stage_instruments.clean(artifact, body.answers),
        overall=overall,
        note=(body.note or "").strip()[:2000] or None,
        job_id=body.job_id,
        curated=body.curated,
    )
    # THE SAME SHAPE THE READ ANSWERS, and that is not tidiness. The client puts this reply
    # straight into the cache as the form's new state, so a reply missing `instrument` left
    # the screen holding a payload with no questions in it — and `StageReview` renders
    # nothing at all without one. Saving made the whole block disappear, and a reload
    # brought it back because the reload went through `read`.
    return _payload(artifact, digest, row)
