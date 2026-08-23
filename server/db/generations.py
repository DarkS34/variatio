"""Every query over the variants the system produced.

Kept apart from `repository.py` — which is about the instance's artifacts — because this
table's rows belong to a *person* as well as to a workspace. That is the whole reason it
exists: a variant nobody can attribute cannot be handed back to whoever asked for it.

The sessions of the blind comparison used to sit beside it under the same roof and now
live in `study/api/queries.py`, next to the arithmetic that reads them.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Generation, User


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
