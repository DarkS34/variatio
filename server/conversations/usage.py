"""How many turns an account has queued today in one conversational function.

The count is the account's across every workspace, because the queue it protects is the
installation's. It lives in the database (`tutor_usage`, one row per account, day and
function) and not in the conversation files: a conversation can be deleted by its author, and
a limit somebody resets by deleting is none. The day is UTC, so the limit reopens at the same
moment for everybody.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.daily import seconds_to_reopen, today, wait_in_words
from server.db.models import TutorUsage


@dataclass(frozen=True)
class Limit:
    """One function's daily count: its name in the table, its refusal's code and its words."""

    feature: str
    code: str
    # What the refusal says the messages went to: «al tutor», «al chat».
    to: str

    def refusal(self, session: Session, user_id: int, limit: int | None) -> tuple[str, int] | None:
        """Return why this account cannot queue a turn now and for how many seconds, or None."""
        if not limit or self.used_today(session, user_id) < limit:
            return None
        wait = seconds_to_reopen()
        return (
            f"Has llegado al límite de {limit} mensajes {self.to} por día. "
            f"Podrás escribir otra vez dentro de {wait_in_words(wait)}.",
            wait,
        )

    def used_today(self, session: Session, user_id: int) -> int:
        """Return how many turns this account has queued today."""
        row = self._row(session, user_id)
        return row.turns if row is not None else 0

    def record(self, session: Session, user_id: int) -> None:
        """Count one more turn queued today by this account."""
        row = self._row(session, user_id)
        if row is None:
            session.add(TutorUsage(user_id=user_id, day=today(), turns=1, feature=self.feature))
        else:
            row.turns += 1
        session.flush()

    def _row(self, session: Session, user_id: int) -> TutorUsage | None:
        """Return today's row of this account for this function, if it queued anything."""
        return session.scalar(
            select(TutorUsage).where(
                TutorUsage.user_id == user_id,
                TutorUsage.day == today(),
                TutorUsage.feature == self.feature,
            )
        )
