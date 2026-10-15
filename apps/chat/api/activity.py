"""The chat's half of a class's weekly activity: its conversations as dated, wordless messages.

`server/activity.py` reaches the chat's conversations through `read`, which
`apps.chat.api.install` sets as its `CHAT_READER`: the server never opens the chat's files
itself. A chat turn is not classified, so each student turn is a date and nothing else — never
its text, never what it was about.
"""

from server import activity
from variatio.core.workspace import Workspace

from .store import STORE, STUDENT


def read(ws: Workspace, user_ids: list[int]) -> list[activity.ChatMessage]:
    """Return these accounts' messages to the chat, as who and when."""
    found: list[activity.ChatMessage] = []
    for user_id in user_ids:
        directory = STORE.author_dir(ws, user_id)
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            summary = activity.cached(path, lambda record, u=user_id: _summary(record, u), STORE.read_file)
            if summary:
                found.extend(summary)
    return found


def _summary(record: dict, user_id: int) -> list[activity.ChatMessage]:
    """Turn one conversation into the dates of its student's messages."""
    moments = (activity.moment_of(turn.get("at")) for turn in record.get("turns") or [] if turn.get("role") == STUDENT)
    return [activity.ChatMessage(user_id=user_id, at=at) for at in moments if at is not None]
