"""The tutor's prompts and fixed texts, in English.

The same names and signatures as `es`, pinned by test, so a workspace's language picks the
set and nothing else changes. Unmeasured, like the rest of the English prompts.
"""

import json

LANGUAGE = "en"

FIXED_RULES: tuple[str, ...] = (
    "Asks at least one guiding question in every reply and at most {max_questions}: about "
    "understanding, design or analysis, or one that leads the student to find their own mistake.",
    "Points to the notes in every reply: names the unit or the section where what the student "
    "needs is, and only one of those the card lists.",
    "Before explaining a concept, briefly checks whether the student knows what it needs. If "
    "they have not seen it, tells them what to look for and where, without explaining it; if "
    "they have, asks them to explain it in their own words. Checks each concept once: if the "
    "student does not answer, does not ask again and carries on from what the student said.",
    "Writes no complete code and no solution that could be copied. At most, quotes one line of "
    "the student's code to ask about it.",
    "Does not run, simulate or debug code, does not calculate, and never says whether something "
    "is right or wrong: not a solution, not an answer, not a definition. Instead of confirming, "
    "asks something that lets the student check it; on seeing a mistake, asks so they find it.",
    "Uses only what is in the notes and on the card. Introduces no concept the syllabus places "
    "after the one being worked on, and no technique, statement or function the material lacks.",
    "Applies the subject's teaching criteria. When the student breaks one, does not correct it: "
    "asks about it and names the section of the notes.",
    "When the student insists on the solution, does not give in: acknowledges the effort and "
    "goes back to a smaller question.",
    "Administrative questions and questions outside the subject get a fixed answer that never "
    "reaches the model.",
)

GOLDEN_RULE = "If the student can copy your reply and move on without thinking, you have failed as a tutor."

DEFAULT_ADMINISTRATIVE_REPLY = (
    "For anything that is not about the content of the subject, please ask your teacher "
    "directly through the course's usual channel."
)

BANK_SOURCE = "Exercise bank"

# How a repair names what it is asked to return, in the repair prompt's own language.
SHAPE_OBJECT = "object"

_KIND_LABELS = {
    "theory": "a question about the theory",
    "exercise": "help with an exercise statement",
    "attempt": "the student's own attempt",
    "solution": "a request for the solution",
    "social": "a greeting or a remark with no content",
}

_KIND_TASKS = {
    "theory": (
        "The student asks about the theory. If needed, first check what they already know; "
        "then lead them with a question towards the section of the notes that explains it."
    ),
    "exercise": (
        "The student brings an exercise statement. Help them understand it: what data it gives, "
        "what it asks for and which concepts of the syllabus it needs. Do not solve it or give "
        "the shape of the solution."
    ),
    "attempt": (
        "The student shows their own attempt. Do not say whether it is right or wrong. If it "
        "breaks a teaching criterion or has a mistake, ask a question that leads them to see it "
        "and name the section of the notes."
    ),
    "solution": (
        "The student asks for the solution. Do not give it. Acknowledge their effort, say in one "
        "sentence why you will not give it, and go back to a small question that moves them on."
    ),
    "social": (
        "The student greets, thanks or remarks on something with no content. Answer in one or two "
        "sentences and ask what they want to work on in the subject."
    ),
}

_FAILURES = {
    "no_question": "it asked no question",
    "too_many_questions": "it asked more than {max_questions} questions",
    "code": "it carried more than {max_code_lines} lines of code",
    "copied": "it copied a passage of the notes instead of pointing to it",
    "later": "it introduced concepts the syllabus places later: {concepts}",
    "forbidden": "it suggested statements the material does not use: {terms}",
    "validated": "it told the student they were right instead of asking something that lets them check it",
    "truncated": "it was too long and was cut",
    "empty": "it came back empty",
}

# A sentence that opens by telling the student they are right, read on folded text.
VALIDATION_PATTERN = (
    r"(?:^|[.!?]\s+)\s*(?:yes\b[,!]?\s*)?(?:exactly|correct|that.s right|right\b|perfect|"
    r"well done|that.s it|you got it|spot on|good job|you are right|you.re right)\b"
)

NORMATIVE_PATTERN = (
    r"\b(?:(?:must|should|do|does|can|may) not|mustn.t|shouldn.t|don.t|never|always|avoid\w*|"
    r"(?:common|typical|frequent|serious) (?:mistake|error)s?|bad practice\w*|good practice\w*|"
    r"mandatory|required|recommended|important|preferable|incorrect\w*|penali[sz]\w*)\b"
)


# THE REPLY -----------------------------------------------------------------------------


def method(max_questions: int) -> str:
    """Return the system prompt every reply is written under."""
    rules = "\n".join(
        f"{index}. {rule.format(max_questions=max_questions)}"
        for index, rule in enumerate(FIXED_RULES[:-1], 1)
    )
    return (
        "You are the Socratic tutor of a subject. Your job is to make the student reason: you "
        "guide them with questions and solve nothing for them.\n\n"
        f"Golden rule: {GOLDEN_RULE}\n\n"
        "In every reply, the tutor:\n"
        f"{rules}\n\n"
        "Style: warm and patient, never condescending nor punitive. Short replies, never the same "
        "formula from one turn to the next. Write in English and address the student directly. "
        "The system writes each turn's card and the student never sees it: do not mention it."
    )


def turn_prompt(card: str, history: list[tuple[str, str]], message: str, kind: str) -> str:
    """Return the prompt of one reply: the card, the recent conversation and what to do now."""
    lines = [card, "", "THE CONVERSATION SO FAR"]
    if history:
        lines += [f"{'Student' if role == 'student' else 'Tutor'}: {text}" for role, text in history]
    else:
        lines.append("(this is the first message)")
    lines += [
        "",
        "THE STUDENT'S MESSAGE",
        message,
        "",
        "WHAT TO DO NOW",
        _KIND_TASKS.get(kind, _KIND_TASKS["theory"]),
        "Reply only with what you would say to the student.",
    ]
    return "\n".join(lines)


def card_block(card) -> str:
    """Render the turn's card, the material code chose for this exact moment of the talk.

    `card` is a `tutor.card.Card`, read by attribute so this module imports nothing of the
    tutor's and both prompt sets stay interchangeable.
    """
    lines = ["THE TURN'S CARD (written by the system from the subject's materials)", ""]
    if card.subject:
        lines += ["Subject:", card.subject, ""]
    lines += [f"Kind of message: {_KIND_LABELS.get(card.kind, card.kind)}.", ""]

    if card.focus:
        lines.append("Focus of the conversation:")
        for concept in card.focus:
            lines.append(f"- «{concept.name}».")
            if concept.definition:
                lines.append(f"  Definition in the notes: {concept.definition}")
            for passage in concept.anchors:
                lines.append(f"  [{_place(passage)}] {passage.text}")
            if concept.prerequisites:
                lines.append(
                    "  Prior knowledge it needs: "
                    + "; ".join(
                        _named_place(p.name, p.location)
                        + (" (already asked)" if p.name in card.verified else "")
                        for p in concept.prerequisites
                    )
                    + "."
                )
            if concept.neighbours:
                lines.append(
                    "  Close concepts, useful to contrast with: "
                    + ", ".join(f"«{c}»" for c in concept.neighbours)
                    + "."
                )
            if concept.later:
                lines.append(
                    "  Comes later in the syllabus (do not introduce it): "
                    + ", ".join(f"«{c}»" for c in concept.later)
                    + "."
                )
        lines.append("")
    else:
        lines += ["Focus of the conversation: none yet.", ""]

    if card.passages:
        lines.append("Passages of the notes related to the message:")
        lines += [f"[{_place(passage)}] {passage.text}" for passage in card.passages]
        lines.append("")

    if card.verified:
        lines += [
            "You already asked the student about: "
            + ", ".join(f"«{c}»" for c in card.verified)
            + ". Do not ask about it again: work with what they answered, even if they "
            "answered something else.",
            "",
        ]

    if card.criteria:
        lines.append("The subject's teaching criteria:")
        lines += [
            f"- ({'required' if c.strength == 'must' else 'recommended'}) {c.text}"
            for c in card.criteria
        ]
        lines.append("")
    if card.forbidden_terms:
        lines += [
            "Statements or functions the material does not use (never suggest them): "
            + ", ".join(card.forbidden_terms)
            + ".",
            "",
        ]

    if card.exercise:
        lines += [
            f"The message is an exercise of the bank ({card.exercise.source}); it works on "
            + ", ".join(f"«{c}»" for c in card.exercise.concepts)
            + ".",
            "",
        ]
    if card.step_down:
        lines += [
            "A simpler exercise on the same concept, to offer only if the student gets stuck "
            f"({card.step_down.source}):",
            card.step_down.statement,
            "",
        ]
    return "\n".join(lines).rstrip()


def retry_note(failures: list[tuple[str, dict]], max_questions: int, max_code_lines: int) -> str:
    """Return the note a second attempt carries, naming what the first one broke."""
    reasons = [
        _FAILURES[code].format(max_questions=max_questions, max_code_lines=max_code_lines, **data)
        for code, data in failures
        if code in _FAILURES
    ]
    return (
        "\n\nYour previous reply was not sent because " + "; ".join(reasons) + ". "
        "Write another one that keeps the tutor's rules."
    )


def fallback_reply(concept: str | None, location: str | None) -> str:
    """Return the question sent when the model failed the checks twice."""
    if concept and location:
        return (
            f"Let's go step by step. What do you remember about «{concept}»? It is in the notes, "
            f"under «{location}»: read it and tell me in your own words what it does."
        )
    if concept:
        return f"Let's go step by step. What do you remember about «{concept}»? Tell me in your own words."
    return "Let's go step by step. Which part of the subject do you want to work on first?"


def off_topic_reply(subject: str, units: list[str]) -> str:
    """Return the fixed answer to a question outside the subject, offering its units."""
    name = f"«{subject}»" if subject else "the subject"
    listing = "\n".join(f"- {unit}" for unit in units)
    offer = f"\n\nShall we work on one of these units?\n{listing}\n\nWhich one first?" if units else (
        "\n\nWhich unit of the subject do you want to work on?"
    )
    return f"That question is outside {name}.{offer}"


def blocked_reply() -> str:
    """Return the fixed answer to a message the guardrail refused."""
    return (
        "I cannot help with that message. If you have a question about the subject, tell me and "
        "we will work on it together. Where do you want to start?"
    )


def _place(passage) -> str:
    """Render where a passage lives: its location, or its document when it has none."""
    return passage.location or passage.document


def _named_place(name: str, location: str | None) -> str:
    """Render a concept with the place of the notes it is explained in, when known."""
    return f"«{name}» (under «{location}»)" if location else f"«{name}»"


# THE CLASSIFICATION --------------------------------------------------------------------


def classify_prompt(subject: str, units: list[str], last_reply: str | None, message: str) -> str:
    """Return the prompt that decides which kind of message the student wrote."""
    return (
        "Classify a student's latest message to the tutor of their subject.\n\n"
        f"Subject:\n{subject or '(no description)'}\n\n"
        f"Units of the syllabus: {'; '.join(units) or '(no units)'}.\n\n"
        f"The tutor's last reply:\n{last_reply or '(none; this is the first message)'}\n\n"
        f"The student's message:\n{message}\n\n"
        "Kinds:\n"
        "- theory: a question or doubt about a concept or content of the subject, or carrying on "
        "with one (also «I don't get it» or an answer to the tutor's question).\n"
        "- exercise: brings an exercise statement, even one worded as an order («Write a program that…»), and asks for help understanding or starting it.\n"
        "- attempt: shows their own code, answer or reasoning and asks for an opinion.\n"
        "- solution: asks for the solution, the complete code or the final answer.\n"
        "- social: greets, thanks or remarks on something with no content of the subject.\n"
        "- administrative: asks about grades, dates, submissions, enrolment, the teacher or how "
        "the course is run.\n"
        "- off_topic: asks about something unrelated to the subject.\n\n"
        'Answer only with the JSON {"kind": "<kind>"}.'
    )


# THE CRITERIA --------------------------------------------------------------------------


def criteria_unit_prompt(
    subject: str,
    unit: str,
    concepts: list[str],
    passages: list[tuple[str, str, str]],
    solutions: list[tuple[str, str, str]],
    max_criteria: int,
) -> str:
    """Return the prompt that drafts one unit's criteria from its notes and its solutions.

    `passages` and `solutions` are `(id, place, text)`: the model cites them by id, and code
    keeps only the criteria whose citations exist.
    """
    notes = "\n\n".join(f"[{pid} · {place}]\n{text}" for pid, place, text in passages) or "(none)"
    banked = "\n\n".join(f"[{sid} · {place}]\n{text}" for sid, place, text in solutions) or "(none)"
    return (
        "You are going to write the teaching criteria of one unit of a subject. A Socratic tutor "
        "will apply them while guiding students: they tell it what the material asks for and "
        "what it avoids.\n\n"
        f"Subject:\n{subject or '(no description)'}\n\n"
        f"Unit: «{unit}»\n"
        f"Concepts of the unit: {', '.join(f'«{c}»' for c in concepts) or '(none)'}.\n\n"
        "Passages of the notes of this unit (cite them by their id):\n"
        f"{notes}\n\n"
        "Solutions of the exercise bank for this unit (cite them by their id):\n"
        f"{banked}\n\n"
        "What a criterion is:\n"
        "- A convention the notes ask for: how to name, how to structure, which construct to use "
        "in each case.\n"
        "- A mistake the notes point out, or a practice they advise against.\n"
        "- A convention ALL the cited solutions follow, even if the notes do not say it.\n\n"
        "Rules:\n"
        f"- Write at most {max_criteria} criteria: the ones that matter most for guiding a student.\n"
        "- Write each criterion in one or two sentences addressed to the tutor, with no complete "
        "programs.\n"
        "- Each criterion cites in \"evidence\" at least one passage or solution that supports it. "
        "No citation, no criterion.\n"
        "- Write nothing from general knowledge that the material does not say.\n"
        "- \"strength\": \"must\" if the material requires it or calls it a mistake; \"should\" if "
        "it recommends it or only warns.\n"
        "- \"scope\": \"subject\" if it holds for the whole subject; \"unit\" if it belongs to "
        "this unit.\n"
        "- \"concepts\": the concepts of the list it refers to; it may stay empty.\n"
        "- \"forbidden\": ONLY names of statements, keywords or functions of the language that "
        "the material forbids or advises against, written as they appear in code (one or two "
        "words, for instance break or global), with the reason and the citation. A practice to "
        "avoid is a criterion, not a term. Empty if there are none.\n\n"
        "Answer only with the JSON."
    )


def criteria_merge_prompt(texts: list[str]) -> str:
    """Return the prompt that groups the subject-wide criteria saying the same thing."""
    numbered = "\n".join(f"{index}. {text}" for index, text in enumerate(texts, 1))
    return (
        "These teaching criteria hold for a whole subject and come from different units, so some "
        "say the same thing in other words.\n\n"
        f"{numbered}\n\n"
        "Group the ones that say the same thing. Each group is the list of its numbers; a "
        "criterion with no match is a group of one. Every number appears exactly once.\n\n"
        'Answer only with the JSON {"groups": [[...], ...]}.'
    )


def schema_text(schema: dict) -> str:
    """Render a JSON schema for a prompt that runs without its grammar."""
    return json.dumps(schema, ensure_ascii=False, indent=2)
