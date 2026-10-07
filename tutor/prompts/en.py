"""The tutor's prompts and fixed texts, in English.

The same names and signatures as `es`, pinned by test, so a workspace's language picks the
set and nothing else changes. Unmeasured, like the rest of the English prompts.
"""

import json

LANGUAGE = "en"

METHOD_RULES: tuple[str, ...] = (
    "Asks at least one guiding question in every reply and at most {max_questions}: about "
    "understanding, design or analysis, or one that leads the student to find their own mistake.",
    "Leans on the notes in every reply: starts from what they say, in its own words («in the "
    "notes, a function is defined as…»). Names no unit, section or document: the system shows "
    "under the reply where it is.",
    "Takes as known what the syllabus places before the concept the student asks about: does "
    "not quiz them on it nor steer the conversation towards it. Works on the concept the "
    "student asked for. Only when the student says something earlier is missing, or their "
    "message shows it, tells them in one sentence to review that concept in the notes, naming "
    "the concept and not the section, without asking about it, and its question goes back to "
    "what the student asked.",
    "Writes no complete code and no solution that could be copied. At most, quotes one line of "
    "the student's code to ask about it.",
    "Does not run, simulate or debug code, does not calculate, and never says whether something "
    "is right or wrong: not a solution, not an answer, not a definition. Instead of confirming, "
    "asks something that lets the student check it; on seeing a mistake, asks so they find it.",
    "Uses only what is in the notes and on the card. Introduces no concept the syllabus places "
    "after the one being worked on, and no technique, statement or function the material lacks.",
    "Applies the subject's teaching criteria. When the student breaks one, does not correct it: "
    "asks about it and points to what the notes say.",
    "When the student insists on the solution, does not give in: acknowledges the effort and "
    "goes back to a smaller question.",
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
        "The student asks about the theory. Work on the concept they ask about, taking what "
        "comes before as known, and lead them with a question towards what the notes say about it."
    ),
    "exercise": (
        "The student brings an exercise statement. Help them understand it: what data it gives, "
        "what it asks for and which concepts of the syllabus it needs. Do not solve it or give "
        "the shape of the solution."
    ),
    "attempt": (
        "The student shows their own attempt. Do not say whether it is right or wrong. If it "
        "breaks a teaching criterion or has a mistake, ask a question that leads them to see it "
        "and point to what the notes say."
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
    "diagram": "it drew a diagram, and the system adds the maps when they help",
    "copied": "it copied a passage of the notes instead of saying it in other words",
    "later": "it introduced concepts the syllabus places later: {concepts}",
    "forbidden": "it suggested statements the material does not use: {terms}",
    "validated": "it told the student they were right instead of asking something that lets them check it",
    "truncated": "it was too long and was cut",
    "empty": "it came back empty",
}

# A sentence that opens by telling the student they are right, read on folded text.
VALIDATION_PATTERN = (
    r"(?:^|[.!?]\s+)\s*(?:yes\b[,!]?\s*)?(?:exactly|correct|that.s right|right\b|perfect|"
    r"well done|that.s it(?=\s*(?:[.!,;:]|$))|you got it|spot on|good job|you are right|"
    r"you.re right)\b"
)

# A sentence that sends the student to go over something again, read on folded text. With a
# prerequisite named in the same sentence, it is what `Card.sent_back` reads as a send-back.
REVIEW_PATTERN = r"\b(?:review\w*|revisit\w*|re-?read\w*|go(?:ing)? back (?:to|over)|brush(?:ing)? up)\b"

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
        for index, rule in enumerate(METHOD_RULES, 1)
    )
    return (
        "You are the Socratic tutor of a subject. Your job is to make the student reason: you "
        "guide them with questions and solve nothing for them.\n\n"
        f"Golden rule: {GOLDEN_RULE}\n\n"
        "In every reply, the tutor:\n"
        f"{rules}\n\n"
        "Style: warm and patient, never condescending nor punitive. Short replies, never the same "
        "formula from one turn to the next. Write in English and address the student directly. "
        "The system writes each turn's card and the student never sees it: do not mention it. "
        "Under your reply the system shows the sections of the notes it comes from, and the "
        "student opens them from there: so write no name of a unit, a section or a document.\n\n"
        "Notation: when what is being worked on is written in mathematical notation (a formula, a "
        "recurrence, a cost), write it between dollar signs, like this: $a^2 + b^2$. Use it only "
        "where it is clearer than the sentence it replaces, once or twice per reply at most, and "
        "never to give the result the student has to find. Draw no diagrams: when a map helps, "
        "the system adds it under your reply."
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
    tutor's and both prompt sets stay interchangeable. The notes are quoted WITHOUT where they
    are: the places are shown under the reply by the system, and a reply cannot repeat a
    heading it never read.
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
                lines.append(f"  In the notes: {passage.text}")
            if concept.prerequisites:
                lines.append(
                    "  Taken as known (do not ask about it; if the student lacks it, only tell "
                    "them to review it in the notes): "
                    + ", ".join(f"«{p.name}»" for p in concept.prerequisites)
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

    if card.chosen:
        lines += [
            f"The student chose «{card.chosen}» as the topic of this message: the message is "
            "about that concept even if it does not name it.",
            "",
        ]

    if card.map_of:
        lines += [
            f"Under your reply the student will see a map of «{card.map_of}»: what is taken as "
            "known, the concept and what comes later. Do not describe it nor repeat it in "
            "words. You may point to it in half a sentence if it helps; there is no need.",
            "",
        ]

    if card.passages:
        lines.append("Passages of the notes related to the message:")
        lines += [f"- {passage.text}" for passage in card.passages]
        lines.append("")

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


def fallback_reply(concept: str | None, placed: bool) -> str:
    """Return the question sent when the model failed the checks twice.

    `placed` says whether a place of the notes will be shown under it.
    """
    if concept and placed:
        return (
            f"Let's go step by step. What do you remember about «{concept}»? It is in the notes, "
            "in the section you see just below: read it and tell me in your own words what it does."
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


# THE TITLE -----------------------------------------------------------------------------


def title_prompt(messages: list[str], concepts: list[str]) -> str:
    """Return the prompt that names a conversation from what the student has written so far."""
    written = "\n\n".join(f"- {text}" for text in messages) or "(none)"
    worked = ", ".join(f"«{c}»" for c in concepts) or "(none)"
    return (
        "Give a title to a conversation between a student and the tutor of their subject.\n\n"
        f"The student's messages:\n{written}\n\n"
        f"Concepts of the syllabus being worked on: {worked}.\n\n"
        "The title says what the conversation is about: the concept or the exercise, not the "
        "greeting nor the way it was asked. Two to six words, in English, in sentence case, "
        "without quotes and without a final full stop.\n\n"
        'Answer only with the JSON {"title": "<title>"}.'
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
        f"- Write at most {max_criteria} criteria: only the ones that matter most for guiding a "
        "student. Fewer is better than many.\n"
        "- Each criterion is ONE sentence of at most 20 words, in plain language, saying what is "
        "asked for or what is avoided. Start with what is asked, without formulas such as "
        "«Require that», «Insist that» or «Remember that». No programs and no lists of cases.\n"
        "- Each criterion cites in \"evidence\" at least one passage or solution that supports it. "
        "No citation, no criterion.\n"
        "- Write nothing from general knowledge that the material does not say.\n"
        "- \"strength\": \"must\" if the material requires it or calls it a mistake; \"should\" if "
        "it recommends it or only warns.\n"
        "- \"scope\": \"subject\" if it holds for the whole subject; \"unit\" if it belongs to "
        "this unit.\n"
        "- \"concepts\": at most three concepts of the list it refers to; it may stay empty.\n"
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


# THE WEEKLY DIGEST -----------------------------------------------------------------------


def digest_prompt(
    concept: str, unit: str | None, messages: list[str], max_themes: int, max_words: int
) -> str:
    """Return the prompt that sums up, for a teacher, what a class asked about one concept in a week."""
    numbered = "\n\n".join(f"[{index}] {text}" for index, text in enumerate(messages, 1))
    placed = f", from the unit «{unit}»" if unit else ""
    return (
        "Sum up for a teacher what their students asked the subject's tutor this week about "
        "one concept.\n\n"
        f"Concept: «{concept}»{placed}.\n\n"
        f"The students' messages, numbered:\n{numbered}\n\n"
        "Write the themes that recur: what they do not understand, where they go wrong, or "
        "what they ask for.\n\n"
        "Rules:\n"
        f"- At most {max_themes} themes, the most frequent first. Fewer is better than many.\n"
        f"- Each theme is ONE sentence of at most {max_words} words, in the third person plural "
        "(«They confuse…», «They ask for…», «They do not see…»).\n"
        "- Write in your own words: do not copy sentences from the messages, not even in quotes.\n"
        "- Name no student and do not say how many they are.\n"
        "- In \"messages\", the numbers of the messages the theme covers.\n"
        "- A message that is not about the subject belongs to no theme.\n\n"
        'Answer only with the JSON {"themes": [{"text": "...", "messages": [1, 2]}]}.'
    )


_DIGEST_FAILURES = {
    "copy": "a theme copied words from a message: write it in your own",
    "name": "a theme named a student: name nobody",
    "long": "a theme went over the number of words",
    "empty": "a theme covered no message of the list",
}


def digest_retry_note(failures: list[str]) -> str:
    """Return the note a second digest call carries, naming what the first got wrong."""
    said = "; ".join(
        _DIGEST_FAILURES[code] for code in dict.fromkeys(failures) if code in _DIGEST_FAILURES
    )
    return f"\n\nThe previous answer was not valid ({said}). Write it again following the rules."


def schema_text(schema: dict) -> str:
    """Render a JSON schema for a prompt that runs without its grammar."""
    return json.dumps(schema, ensure_ascii=False, indent=2)
