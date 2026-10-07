"""The tutor's half of a class's weekly activity: its conversations as dated, wordless messages.

`server/activity.py` counts what a subject's students do for its teachers, and reaches the
conversations through `read`, which `tutor.api.install` sets as its `TUTOR_READER`: the
server never opens the tutor's files itself. Each student turn becomes a `Message` with its
date, the kind of reply it got, the concept it was about and the prerequisite it was sent back
to — never its text, which only the digest's job reads, from the file, when a teacher asks.
"""

from server import activity
from variatio.core.workspace import Workspace

from .. import ADMINISTRATIVE, BLOCKED, OFF_TOPIC, SOCIAL
from . import store

# The kinds of reply that do not work on the subject: counted, never grouped by concept nor
# summarised.
OFF_SUBJECT = frozenset({SOCIAL, ADMINISTRATIVE, OFF_TOPIC, BLOCKED})


def read(ws: Workspace, user_ids: list[int]) -> activity.TutorReading:
    """Return these accounts' messages to the tutor, and the exercises they took to it."""
    messages: list[activity.Message] = []
    taken: set[str] = set()
    for user_id in user_ids:
        directory = store.author_dir(ws, user_id)
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            summary = activity.cached(
                path, lambda record, u=user_id: _summary(record, u), store.read_file
            )
            if summary is None:
                continue
            found, opened = summary
            messages.extend(found)
            if opened:
                taken.add(opened)
    return activity.TutorReading(messages, frozenset(taken))


def _summary(record: dict, user_id: int) -> tuple[list[activity.Message], str | None]:
    """Turn one conversation into its student's messages and the exercise it was opened on."""
    conversation = str(record.get("id") or "")
    turns = record.get("turns") or []
    found = []
    for index, turn in enumerate(turns):
        if turn.get("role") != store.STUDENT:
            continue
        at = activity.moment_of(turn.get("at"))
        if at is None:
            continue
        following = turns[index + 1] if index + 1 < len(turns) else None
        reply = following if following and following.get("role") == store.TUTOR else None
        kind = (reply or {}).get("kind")
        on_subject = kind is not None and kind not in OFF_SUBJECT
        found.append(
            activity.Message(
                user_id=user_id,
                conversation=conversation,
                turn=index,
                at=at,
                kind=kind,
                on_subject=on_subject,
                concept=turn.get("concept") or (_focus(reply) if on_subject else None),
                sent_back=_sent_back(reply),
            )
        )
    opened = record.get("opened_from") or {}
    generation = opened.get("generation_id") if opened.get("kind") == "generation" else None
    return found, (str(generation) if generation else None)


def _focus(reply: dict | None) -> str | None:
    """Return the concept a reply stood on: the first of its card's focus."""
    concepts = ((reply or {}).get("card") or {}).get("concepts") or []
    return str(concepts[0]) if concepts else None


def _sent_back(reply: dict | None) -> str | None:
    """Return the prerequisite a reply sent the student back to review, if it did.

    Read off the turn since 2026-10-07; an older turn says it only where its map was drawn.
    """
    if not reply:
        return None
    sent = reply.get("sent_back")
    if isinstance(sent, list) and len(sent) == 2:
        return str(sent[1])
    the_map = reply.get("concept_map") or {}
    return str(the_map["review"]) if the_map.get("review") else None
