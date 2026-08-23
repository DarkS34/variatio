from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.db.models import EvalSession, User


def _moment(timestamp: float | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def upsert_evaluation(
    session: Session,
    session_id: str,
    workspace_id: int,
    user_id: int | None,
    payload: dict,
) -> EvalSession:
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
    row.choice = payload.get("choice")
    row.choice_arm = payload.get("choice_arm")
    row.chosen_at = payload.get("chosen_at")
    row.evaluator_note = payload.get("evaluator_note")
    row.rating = payload.get("rating")
    row.arm_status = {
        name: arm.get("status") for name, arm in (payload.get("arms") or {}).items()
    }
    row.arm_elapsed_ms = {
        name: arm.get("elapsed_ms") for name, arm in (payload.get("arms") or {}).items()
    }
    row.trace = payload
    session.flush()
    return row


def get_evaluation(session: Session, session_id: str) -> EvalSession | None:
    return session.get(EvalSession, session_id)


def list_evaluations(
    session: Session,
    workspace_id: int | None = None,
    author: int | None = None,
    limit: int | None = 50,
    offset: int = 0,
) -> tuple[list[EvalSession], int]:
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


# The whole population, for the analysis: no pagination, because an aggregate computed
# over one page is not an aggregate. Loaded with its author so grouping by account does
# not fire one query per row.
def all_evaluations(
    session: Session, workspace_id: int | None = None
) -> list[tuple[EvalSession, User | None]]:
    query = (
        select(EvalSession, User)
        .outerjoin(User, User.id == EvalSession.user_id)
        .order_by(EvalSession.created_at.asc())
    )
    if workspace_id is not None:
        query = query.where(EvalSession.workspace_id == workspace_id)
    return [(row, user) for row, user in session.execute(query)]
