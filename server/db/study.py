"""Every query over what the system produced: generated variants and blind comparisons.

Kept apart from `repository.py` — which is about the instance's artifacts — because these
two tables are the only ones whose rows belong to a *person* as well as to a workspace.
That is the whole reason they exist: a variant nobody can attribute cannot be handed back
to whoever asked for it, and a comparison nobody can attribute cannot be grouped by
account, which is the question the study asks.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import EvalSession, Generation, User


def _moment(timestamp: float | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


# GENERATIONS ---------------------------------------------------------------------------


def save_generation(
    session: Session,
    workspace_id: int,
    user_id: int | None,
    job_id: str | None,
    item_type: str,
    item: dict,
    concepts: list[str],
    curriculum: list[str],
    fixed: dict,
    instructions: str | None,
    think: bool,
    thinking: str | None,
    checks: dict | None = None,
) -> Generation:
    row = Generation(
        workspace_id=workspace_id,
        user_id=user_id,
        job_id=job_id,
        item_type=item_type or "",
        concepts=list(concepts or []),
        curriculum=list(curriculum or []),
        fixed=dict(fixed or {}),
        instructions=instructions or None,
        think=bool(think),
        item=item,
        thinking=thinking or None,
        checks=checks or None,
    )
    session.add(row)
    session.flush()
    return row


# `author` narrows to one account, `None` means the whole workspace. The caller decides
# which, because "mine" and "everything here" are two legitimate readings of a shared
# instance and neither can be inferred from the row.
def list_generations(
    session: Session,
    workspace_id: int,
    author: int | None = None,
    concept: str | None = None,
    item_type: str | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Generation, User | None]], int]:
    conditions = [Generation.workspace_id == workspace_id]
    if author is not None:
        conditions.append(Generation.user_id == author)
    if item_type:
        conditions.append(Generation.item_type == item_type)

    rows = list(
        session.execute(
            select(Generation, User)
            .outerjoin(User, User.id == Generation.user_id)
            .where(*conditions)
            .order_by(Generation.created_at.desc(), Generation.id.desc())
        )
    )

    # Concept and free text are filtered in Python rather than in SQL: `concepts` is a
    # JSON array and `item` a document whose fields the exemplars profile decides, so a
    # portable predicate would have to be written per dialect. A workspace's generations
    # are counted in the thousands at most, which is nothing to scan.
    pairs = [(row, user) for row, user in rows]
    if concept:
        pairs = [(g, u) for g, u in pairs if concept in (g.concepts or [])]
    if query:
        needle = query.lower()
        pairs = [(g, u) for g, u in pairs if needle in _searchable(g)]

    return pairs[offset : offset + limit], len(pairs)


def _searchable(row: Generation) -> str:
    parts = [str(value) for value in (row.item or {}).values() if isinstance(value, str)]
    parts.extend(row.concepts or [])
    parts.append(row.instructions or "")
    return " ".join(parts).lower()


def get_generation(session: Session, generation_id: int) -> Generation | None:
    return session.get(Generation, generation_id)


def delete_generation(session: Session, row: Generation) -> None:
    session.delete(row)
    session.flush()


def count_generations(session: Session, workspace_id: int | None = None) -> int:
    query = select(func.count(Generation.id))
    if workspace_id is not None:
        query = query.where(Generation.workspace_id == workspace_id)
    return session.scalar(query) or 0


def generations_per_user(session: Session) -> dict[int, int]:
    rows = session.execute(
        select(Generation.user_id, func.count(Generation.id)).group_by(Generation.user_id)
    )
    return {user_id: count for user_id, count in rows if user_id is not None}


# EVALUATION SESSIONS -------------------------------------------------------------------


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
