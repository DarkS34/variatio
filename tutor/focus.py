"""The focus: which concepts of the graph a conversation is about, turn after turn.

It belongs to the CONVERSATION and not to a message. A message alone is often no topic at
all — «no lo entiendo», «¿y eso por qué?» — and re-deciding the focus from it would move the
card to whatever concept that sentence happens to resemble. So a focus is set once, by the
first message that clearly names one, and moves only when a later message is clearly about
another: its best concept has to clear the threshold AND beat the current focus on that same
message by a margin.

A message about something the syllabus places BEFORE the focus never moves it. What comes
before is taken as known: a student asking about recursion who answers a question about
functions is still working on recursion, and a focus that followed them back made the next
card about functions and the tutor walk them through the prerequisites one by one. The card
keeps every direct prerequisite with where the notes explain it, which is all a reply needs
to send a student who says one is missing to the right section.

Two other things move it, neither of them the model's say-so. A message that IS a bank
exercise brings that exercise's tagged concepts, read off the artifacts. And the student may
say outright what a message is about, by choosing a concept beside the box they write in
(`with_chosen`): nothing is deduced then, the chosen concept leads.
"""

MAX_FOCUS = 2


def next_focus(
    current: list[str],
    scores: dict[str, float],
    *,
    threshold: float,
    margin: float,
    eligible: set[str],
    before: set[str] | None = None,
    given: list[str] | None = None,
) -> list[str]:
    """Return the focus a turn is answered with.

    `given` are concepts the turn already knows the message is about — a bank exercise's
    tags, a generated exercise's targets — and they win outright. Otherwise the scores of
    the message decide, against `current`, within `eligible` (the graph's concepts minus the
    generic ones, which name no topic anybody can work on); a best concept in `before` — the
    prerequisite closure of the current focus — keeps the focus where it is.
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
    if current and before and best in before:
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


def with_chosen(
    chosen: str,
    scores: dict[str, float],
    *,
    threshold: float,
    eligible: set[str],
    before: set[str] | None = None,
) -> list[str]:
    """Return the focus of a message the student sent about a concept they chose.

    The chosen concept leads, whatever the message scores. One other concept may join it:
    the message's own best one, when it clears the threshold — «¿en qué se diferencia de un
    procedimiento?» sent about «Función» is about both, and choosing must not cost the
    student the contrast. Never one of `before`, the chosen concept's prerequisite closure:
    what comes before is taken as known here as everywhere.
    """
    ranked = sorted(
        (
            (str(name), float(score))
            for name, score in scores.items()
            if name in eligible and name != chosen and name not in (before or set())
        ),
        key=lambda pair: -pair[1],
    )
    second = [ranked[0][0]] if ranked and ranked[0][1] >= threshold else []
    return [chosen, *second][:MAX_FOCUS]


def after_reply(state: dict, focus: list[str], drawn: list[str] | None = None) -> dict:
    """Return the conversation's state once a reply is written.

    The trail keeps every concept the conversation has stood on, in order, for whoever reads
    the conversation afterwards. `drawn` are the keys of the concept map shown under this
    reply, if one was (`tutor.concept_map`): `mapped` remembers them so no map is shown
    twice, and `since_map` counts the replies since the last one — absent until a first map
    is shown, since there is nothing yet to keep a distance from.
    """
    trail = list(state.get("trail", []))
    for name in focus:
        if name not in trail[-MAX_FOCUS:]:
            trail.append(name)
    after = {
        "focus": list(focus)[:MAX_FOCUS],
        "trail": trail,
        "mapped": list(dict.fromkeys([*(state.get("mapped") or []), *(drawn or [])])),
    }
    if drawn:
        after["since_map"] = 0
    elif "since_map" in state:
        after["since_map"] = int(state["since_map"]) + 1
    return after
