"""Every read and write of the `stage_evaluations` table, and nothing else.

The unique constraint is over `(workspace, user, artifact, artifact_hash)`, so every write
here is an upsert against the build that was on screen: answering the same build twice
corrects one row, and answering after a REBUILD opens a new one. That is the whole reason
the hash is part of the key rather than a column beside it.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.db.models import StageEvaluation, User, Workspace


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def mine(
    session: Session,
    workspace_id: int,
    user_id: int | None,
    artifact: str,
    artifact_hash: str | None,
) -> StageEvaluation | None:
    """This person's row for this build of this artifact, or nothing."""
    return session.scalars(
        select(StageEvaluation).where(
            StageEvaluation.workspace_id == workspace_id,
            StageEvaluation.user_id == user_id,
            StageEvaluation.artifact == artifact,
            StageEvaluation.artifact_hash == artifact_hash,
        )
    ).one_or_none()


def mark_opened(
    session: Session,
    workspace_id: int,
    user_id: int | None,
    artifact: str,
    artifact_hash: str | None,
) -> StageEvaluation:
    """Record that the questions reached this person, without moving an earlier stamp.

    A row exists from the moment the form is SEEN rather than from the moment it is
    answered, and that is deliberate: «lo abrió y no lo contestó» is a datum about whether
    a panel of teachers will engage at all, and a table that only holds finished forms
    cannot express it. `overall is None` is what «sin contestar» means from here on.
    """
    row = mine(session, workspace_id, user_id, artifact, artifact_hash)
    if row is None:
        row = StageEvaluation(
            workspace_id=workspace_id,
            user_id=user_id,
            artifact=artifact,
            artifact_hash=artifact_hash,
            opened_at=_now().timestamp(),
        )
        session.add(row)
        session.flush()
    elif row.opened_at is None:
        row.opened_at = _now().timestamp()
    return row


def save(
    session: Session,
    workspace_id: int,
    user_id: int | None,
    artifact: str,
    artifact_hash: str | None,
    *,
    instrument: str,
    answers: dict,
    overall: int | None,
    note: str | None,
    job_id: str | None = None,
) -> StageEvaluation:
    """Write this person's answers about this build, replacing whatever they said before."""
    row = mark_opened(session, workspace_id, user_id, artifact, artifact_hash)
    row.instrument = instrument
    row.answers = answers
    row.overall = overall
    row.note = note or None
    if job_id:
        row.job_id = job_id
    row.updated_at = _now()
    session.flush()
    return row


def for_workspace(session: Session, workspace_id: int) -> list[StageEvaluation]:
    """Every answered row of one workspace, newest first — the panel's per-instance read."""
    return list(
        session.scalars(
            select(StageEvaluation)
            .where(
                StageEvaluation.workspace_id == workspace_id,
                StageEvaluation.overall.is_not(None),
            )
            .order_by(StageEvaluation.created_at.desc())
        )
    )


def all_rows(session: Session) -> list[tuple[StageEvaluation, str, str | None]]:
    """Every row of the installation with its workspace slug and evaluator, for the export.

    Unanswered rows are INCLUDED here and excluded from `for_workspace`: the panel counts
    verdicts, while the export is research data and «se abrió y se abandonó» is one of the
    things it is for.
    """
    rows = session.execute(
        select(StageEvaluation, Workspace.slug, User.username)
        .join(Workspace, StageEvaluation.workspace_id == Workspace.id)
        .outerjoin(User, StageEvaluation.user_id == User.id)
        .order_by(StageEvaluation.created_at.asc())
    ).all()
    return [(row, slug, username) for row, slug, username in rows]
