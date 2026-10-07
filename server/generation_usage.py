"""How many exercises an account has asked for today, for a student's daily limit.

The count is the account's across every subject, because the queue it protects is the
installation's. It lives in the database (`generation_usage`) and not in the exercise files: a
file can be deleted by its author, and a limit somebody resets by deleting is none. What is
counted is what a commission ASKS for when it is queued; a batch cancelled or failed gives
nothing back, as a tutor's turn does not.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import daily
from .db.models import GenerationUsage

# What a refusal for the day carries in `X-Error-Code`.
LIMIT_CODE = "generation_daily_limit"


@dataclass(frozen=True)
class Refusal:
    """Why a commission cannot be queued today: a status, its code, its sentence, its wait."""

    status: int
    code: str | None
    message: str
    retry_after: int | None


def refusal(session: Session, user_id: int, limit: int | None, wanted: int) -> Refusal | None:
    """Say why this account cannot ask for `wanted` more today, or None when it can.

    Nothing left is a 429 with the wait until the day reopens. Some left, but fewer than asked,
    is a 422 naming how many: the commission can go now, smaller.
    """
    if not limit:
        return None
    used = used_today(session, user_id)
    if used + wanted <= limit:
        return None
    left = max(0, limit - used)
    if left:
        return Refusal(
            422,
            None,
            f"Hoy te quedan {left} de los {limit} ejercicios que puedes pedir al día: "
            f"pide {left} o menos.",
            None,
        )
    wait = daily.seconds_to_reopen()
    return Refusal(
        429,
        LIMIT_CODE,
        f"Has llegado al límite de {limit} ejercicios por día. "
        f"Podrás pedir más dentro de {daily.wait_in_words(wait)}.",
        wait,
    )


def used_today(session: Session, user_id: int) -> int:
    """Return how many exercises this account has asked for today."""
    row = _row(session, user_id)
    return row.items if row is not None else 0


def record(session: Session, user_id: int, items: int) -> None:
    """Count `items` more exercises asked for today by this account."""
    row = _row(session, user_id)
    if row is None:
        session.add(GenerationUsage(user_id=user_id, day=daily.today(), items=items))
    else:
        row.items += items
    session.flush()


def _row(session: Session, user_id: int) -> GenerationUsage | None:
    """Return today's row of this account, if it has asked for anything today."""
    return session.scalar(
        select(GenerationUsage).where(
            GenerationUsage.user_id == user_id, GenerationUsage.day == daily.today()
        )
    )
