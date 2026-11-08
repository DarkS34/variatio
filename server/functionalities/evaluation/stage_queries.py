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
    curated: bool | None = None,
) -> StageEvaluation:
    """Write this person's answers about this build, replacing whatever they said before.

    `curated` only ever climbs the ladder "nobody said" < "no" < "yes". Having corrected
    the artifact by hand is something that HAPPENED, so a later save that stays silent, or
    that says no because the correction was made in an earlier visit, must not erase a yes
    already recorded — otherwise fixing a typo in the note an hour later moves the row into
    the other half of the contrast the column exists for.
    """
    row = mark_opened(session, workspace_id, user_id, artifact, artifact_hash)
    row.instrument = instrument
    row.answers = answers
    row.overall = overall
    row.note = note or None
    if curated:
        row.curated = True
    elif curated is not None and row.curated is None:
        row.curated = False
    if job_id:
        row.job_id = job_id
    row.updated_at = _now()
    session.flush()
    return row


def mark_opened(
    session: Session,
    workspace_id: int,
    user_id: int | None,
    artifact: str,
    artifact_hash: str | None,
) -> StageEvaluation:
    """Record that the questions reached this person, without moving an earlier stamp.

    A row exists from the moment the form is SEEN rather than from the moment it is
    answered, and that is deliberate: "opened it and never answered" is a datum about whether
    a panel of teachers will engage at all, and a table that only holds finished forms
    cannot express it. `overall is None` is what "sin contestar" means from here on.
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


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


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
    verdicts, while the export is research data and "opened and abandoned" is one of the
    things it is for.
    """
    rows = session.execute(
        select(StageEvaluation, Workspace.slug, User.username)
        .join(Workspace, StageEvaluation.workspace_id == Workspace.id)
        .outerjoin(User, StageEvaluation.user_id == User.id)
        .order_by(StageEvaluation.created_at.asc())
    ).all()
    return [(row, slug, username) for row, slug, username in rows]


def everything(
    session: Session, workspace_id: int | None = None
) -> list[tuple[StageEvaluation, Workspace, User | None]]:
    """Every row with its workspace and its author, for the panel's aggregates.

    Unlike `all_rows` it hands over the USER and not only a username, because the panel
    groups by evaluator profile and that is a property of the account; and it takes the
    optional workspace the panel filters on, so the narrowing happens in the query.
    """
    statement = (
        select(StageEvaluation, Workspace, User)
        .join(Workspace, StageEvaluation.workspace_id == Workspace.id)
        .outerjoin(User, StageEvaluation.user_id == User.id)
        .order_by(StageEvaluation.created_at.asc())
    )
    if workspace_id is not None:
        statement = statement.where(StageEvaluation.workspace_id == workspace_id)
    return [(row, workspace, user) for row, workspace, user in session.execute(statement).all()]


def delete_for_accounts(session: Session, account_ids: list[int]) -> int:
    """Delete every form these accounts answered or opened, and count them."""
    if not account_ids:
        return 0
    rows = list(
        session.scalars(select(StageEvaluation).where(StageEvaluation.user_id.in_(account_ids)))
    )
    for row in rows:
        session.delete(row)
    session.flush()
    return len(rows)
