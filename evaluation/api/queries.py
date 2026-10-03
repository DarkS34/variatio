"""Every read and write of the `evaluation_sessions` table, and nothing else.

The header/trace split of the file era survives as columns beside a `trace` JSONB, so
listing a hundred sessions still does not load a hundred prompts.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.db.models import EvalSession, User


def upsert_evaluation(
    session: Session,
    session_id: str,
    workspace_id: int,
    user_id: int | None,
    payload: dict,
) -> EvalSession:
    """Create or overwrite the row for one session, copying the trace into its columns.

    `created_at` is written only when the row is new, so a later save never moves it.
    """
    row = session.get(EvalSession, session_id)
    if row is None:
        row = EvalSession(id=session_id, workspace_id=workspace_id, user_id=user_id)
        session.add(row)
        created = _moment(payload.get("created_at"))
        if created is not None:
            row.created_at = created

    row.job_id = payload.get("job_id")
    row.item_type = payload.get("item_type") or ""
    row.concepts = list(payload.get("concepts") or [])
    row.curriculum = list(payload.get("curriculum") or [])
    row.fixed = dict(payload.get("fixed") or {})
    row.instructions = payload.get("instructions") or None
    row.seed = int(payload.get("seed") or 0)
    row.shuffle = list(payload.get("shuffle") or [])
    row.think = bool(payload.get("think", True))
    row.set_id = payload.get("set_id") or session_id
    row.assigned_by = payload.get("assigned_by")
    row.triage = dict(payload.get("triage") or {})
    row.choice = payload.get("choice")
    row.choice_arm = payload.get("choice_arm")
    row.chosen_at = payload.get("chosen_at")
    row.opened_at = payload.get("opened_at")
    row.declined_at = payload.get("declined_at")
    row.evaluator_note = payload.get("evaluator_note")
    row.rating = payload.get("rating")
    row.arm_status = _per_arm(payload, "status")
    row.arm_elapsed_ms = _per_arm(payload, "elapsed_ms")
    row.trace = payload
    session.flush()
    return row


def _moment(timestamp: float | None) -> datetime | None:
    """Turn a POSIX timestamp into an aware UTC datetime, or None."""
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _per_arm(payload: dict, field: str) -> dict:
    """Pull one field out of every arm's result, for the columns the listing reads."""
    return {name: arm.get(field) for name, arm in (payload.get("arms") or {}).items()}


def get_evaluation(session: Session, session_id: str) -> EvalSession | None:
    """Return one session's row by id, or None."""
    return session.get(EvalSession, session_id)


def delete_evaluations(session: Session, session_ids: list[str]) -> list[str]:
    """Delete the sessions that exist and return the ids actually removed."""
    if not session_ids:
        return []
    rows = list(session.scalars(select(EvalSession).where(EvalSession.id.in_(session_ids))))
    for row in rows:
        session.delete(row)
    session.flush()
    return [row.id for row in rows]


def delete_for_accounts(session: Session, account_ids: list[int]) -> int:
    """Delete every session these accounts hold, across the installation, and count them.

    The evaluator's RECORDS and not the evaluator: the account stays, and so does
    everything else it produced. Stock nobody holds has no `user_id` and is untouched.
    """
    if not account_ids:
        return 0
    rows = list(session.scalars(select(EvalSession).where(EvalSession.user_id.in_(account_ids))))
    for row in rows:
        session.delete(row)
    session.flush()
    return len(rows)


def list_evaluations(
    session: Session,
    workspace_id: int | None = None,
    author: int | None = None,
    limit: int | None = 50,
    offset: int = 0,
) -> tuple[list[EvalSession], int]:
    """Return one page of sessions, newest first, with the total the filters match."""
    conditions = []
    if workspace_id is not None:
        conditions.append(EvalSession.workspace_id == workspace_id)
    if author is not None:
        conditions.append(EvalSession.user_id == author)

    total = session.scalar(select(func.count(EvalSession.id)).where(*conditions)) or 0
    query = (
        select(EvalSession)
        .where(*conditions)
        .order_by(EvalSession.created_at.desc(), EvalSession.id.desc())
        .offset(offset)
    )
    if limit is not None:
        query = query.limit(limit)
    return list(session.scalars(query)), total


def all_evaluations(
    session: Session, workspace_id: int | None = None
) -> list[tuple[EvalSession, User | None]]:
    """Return the whole population with its authors, unpaginated.

    An aggregate computed over one page is not an aggregate, and the join is what keeps
    grouping by account from firing one query per row.
    """
    query = (
        select(EvalSession, User)
        .outerjoin(User, User.id == EvalSession.user_id)
        .order_by(EvalSession.created_at.asc())
    )
    if workspace_id is not None:
        query = query.where(EvalSession.workspace_id == workspace_id)
    return [(row, user) for row, user in session.execute(query)]


def sessions_in_set(session: Session, set_id: str) -> list[EvalSession]:
    """Return every session holding these items, whoever it belongs to.

    The agreement between evaluators is computed from this, and it is the one query that
    ignores who is asking — which is why the evaluator's own router never reaches it.
    """
    return list(
        session.scalars(
            select(EvalSession)
            .where(EvalSession.set_id == set_id)
            .order_by(EvalSession.created_at.asc())
        )
    )


def assigned_to(
    session: Session, workspace_id: int, user_id: int, pending_only: bool = False
) -> list[EvalSession]:
    """Return what this evaluator was handed, oldest first.

    A queue is worked from the front, so "la siguiente" has to mean the same thing on
    every reload.
    """
    query = select(EvalSession).where(
        EvalSession.workspace_id == workspace_id,
        EvalSession.user_id == user_id,
        EvalSession.assigned_by.is_not(None),
    )
    if pending_only:
        query = query.where(
            EvalSession.chosen_at.is_(None), EvalSession.declined_at.is_(None)
        )
    return list(session.scalars(query.order_by(EvalSession.created_at.asc())))


def sets_in_workspace(session: Session, workspace_id: int) -> list[EvalSession]:
    """Return one representative row per distinct set, for the panel that hands them out.

    The earliest row of a set is when those items came into existence, which is what
    the administrator is choosing between.
    """
    rows = session.scalars(
        select(EvalSession)
        .where(EvalSession.workspace_id == workspace_id)
        .order_by(EvalSession.created_at.asc())
    )
    seen: dict[str, EvalSession] = {}
    for row in rows:
        seen.setdefault(row.set_id or row.id, row)
    return list(seen.values())
