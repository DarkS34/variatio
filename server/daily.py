"""The UTC day a daily limit counts under, and the wait until the next one opens.

Shared by the two limits per account and day — the tutor's turns and a student's exercises —
so both reopen at the same moment for everybody and say the same wait in the same words.
"""

from datetime import date, datetime, timedelta, timezone


def wait_in_words(seconds: int) -> str:
    """Say a wait in hours and minutes, never under one minute, as the screens round it."""
    hours, minutes = divmod(max(seconds // 60, 1), 60)
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"


def seconds_to_reopen() -> int:
    """Return how many seconds are left of today."""
    current = now()
    tomorrow = datetime.combine(current.date() + timedelta(days=1), datetime.min.time(), timezone.utc)
    return int((tomorrow - current).total_seconds()) + 1


def today() -> date:
    """Return the day something done now is counted under."""
    return now().date()


def now() -> datetime:
    """Return the present moment, in UTC."""
    return datetime.now(timezone.utc)
