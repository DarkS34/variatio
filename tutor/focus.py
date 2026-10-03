"""The focus: which concepts of the graph a conversation is about, turn after turn.

It belongs to the CONVERSATION and not to a message. A message alone is often no topic at
all — «no lo entiendo», «¿y eso por qué?» — and re-deciding the focus from it would move the
card to whatever concept that sentence happens to resemble. So a focus is set once, by the
first message that clearly names one, and moves only when a later message is clearly about
another: its best concept has to clear the threshold AND beat the current focus on that same
message by a margin.

One other thing moves it, read off the artifacts and not off the model's say-so: a message
that IS a bank exercise brings that exercise's tagged concepts. A reply that asks about one
of the focus's prerequisites does NOT move it — the card already carries every prerequisite
with where the notes explain it, which is all a step back through the graph needs, and a
prerequisite pulled into the focus made the next card about it and the tutor ask it again.
The prerequisite is remembered as checked instead, and the next cards say so.
"""

import re

from variatio.core.lexicon import mentions

MAX_FOCUS = 2

# A question of a reply: from the end of the previous sentence to its question mark.
_QUESTION = re.compile(r"[^.!?\n]*\?")


def next_focus(
    current: list[str],
    scores: dict[str, float],
    *,
    threshold: float,
    margin: float,
    eligible: set[str],
    given: list[str] | None = None,
) -> list[str]:
    """Return the focus a turn is answered with.

    `given` are concepts the turn already knows the message is about — a bank exercise's
    tags, a generated exercise's targets — and they win outright. Otherwise the scores of
    the message decide, against `current`, within `eligible` (the graph's concepts minus the
    generic ones, which name no topic anybody can work on).
    """
    current = [name for name in current if name in eligible]
    if given:
        return [name for name in dict.fromkeys(given) if name in eligible][:MAX_FOCUS] or current

    ranked = sorted(
        ((str(name), float(score)) for name, score in scores.items() if name in eligible),
        key=lambda pair: -pair[1],
    )
    if not ranked or ranked[0][1] < threshold:
        return current

    best, best_score = ranked[0]
    if best in current:
        return current
    if current:
        held = max(scores.get(name, 0.0) for name in current)
        if best_score - held <= margin:
            return current

    focus = [best]
    if len(ranked) > 1:
        second, second_score = ranked[1]
        if second_score >= threshold and best_score - second_score <= margin:
            focus.append(second)
    return focus[:MAX_FOCUS]


def after_reply(state: dict, focus: list[str], prerequisites: list[str], reply: str, wording) -> dict:
    """Return the conversation's state once a reply is written.

    A prerequisite the reply ASKS about is recorded as checked, which the next cards say so
    the tutor does not check it again. Only the reply's questions are read: its other
    sentences cite places of the notes, and a heading such as «Funciones y recursividad»
    would mark as checked a concept nobody asked about. The trail keeps every concept the
    conversation has stood on, in order, for whoever reads the conversation afterwards.
    """
    questions = " ".join(_QUESTION.findall(reply))
    named = [name for name in prerequisites if mentions(questions, name, wording)]
    verified = list(dict.fromkeys([*state.get("verified", []), *named]))
    trail = list(state.get("trail", []))
    for name in focus:
        if name not in trail[-MAX_FOCUS:]:
            trail.append(name)
    return {"focus": list(focus)[:MAX_FOCUS], "trail": trail, "verified": verified}
