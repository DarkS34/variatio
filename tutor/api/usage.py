"""How many turns an account has queued today, for the installation's daily limit.

The count is the account's across every workspace, because the queue it protects is the
installation's. It lives in the database (`tutor_usage`) and not in the conversation files: a
conversation can be deleted by its author, and a limit somebody resets by deleting is none.
The day is UTC, so the limit reopens at the same moment for everybody.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.db.models import TutorUsage

# What a refused turn carries in `X-Error-Code`.
LIMIT_CODE = "tutor_daily_limit"


def refusal(session: Session, user_id: int, limit: int | None) -> tuple[str, int] | None:
    """Return why this account cannot queue a turn now and for how many seconds, or None."""
    if not limit or used_today(session, user_id) < limit:
        return None
    wait = seconds_to_reopen()
    hours, minutes = divmod(max(wait // 60, 1), 60)
    span = f"{hours} h {minutes} min" if hours else f"{minutes} min"
    return (
        f"Has llegado al límite de {limit} mensajes al tutor por día. "
        f"Podrás escribir otra vez dentro de {span}.",
        wait,
    )


def used_today(session: Session, user_id: int) -> int:
    """Return how many turns this account has queued today."""
    row = _row(session, user_id)
    return row.turns if row is not None else 0


def record(session: Session, user_id: int) -> None:
    """Count one more turn queued today by this account."""
    row = _row(session, user_id)
    if row is None:
        session.add(TutorUsage(user_id=user_id, day=today(), turns=1))
    else:
        row.turns += 1
    session.flush()


def seconds_to_reopen() -> int:
    """Return how many seconds are left of today."""
    current = now()
    tomorrow = datetime.combine(current.date() + timedelta(days=1), datetime.min.time(), timezone.utc)
    return int((tomorrow - current).total_seconds()) + 1


def today():
    """Return the day a turn queued now is counted under."""
    return now().date()


def now() -> datetime:
    """Return the present moment, in UTC."""
    return datetime.now(timezone.utc)


def _row(session: Session, user_id: int) -> TutorUsage | None:
    """Return today's row of this account, if it has queued anything today."""
    return session.scalar(
        select(TutorUsage).where(TutorUsage.user_id == user_id, TutorUsage.day == today())
    )
