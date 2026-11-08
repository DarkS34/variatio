"""The free chat's prompts in English."""

from . import conversation as shared


def system_prompt(subject: str, language: str, code: bool) -> str:
    """Return the chat's standing instructions over the blocks every chat-like consumer shares.

    No method: it explains, solves and writes code as the student asks (the user's decision,
    2026-10-14). What it refuses, it refuses in one sentence and goes on helping. Since
    2026-11-02 it answers in the subject's language, as the tutor does (plan §12).
    """
    role = (
        "You are the assistant of a course. You help a student with whatever they ask about the "
        "course or about how to study it: you explain concepts, solve exercises step by step, "
        "suggest examples and practice, and correct what the student has done."
    )
    method = (
        "HOW YOU HELP\n"
        "- Answer clearly and without detours. When you solve something, explain the steps.\n"
        "- If you are not sure of a fact, say so. Do not invent facts, sources or mnemonics, and "
        "do not accept an attempt that has an error in it."
    )
    return shared.system_prompt(role, method, subject=subject, language=language, code=code)


def exercise_block(fields: list[tuple[str, str]]) -> str:
    """Render the exercise the conversation was opened on, with the fields the student reads."""
    lines = ["EXERCISE THE STUDENT OPENED THE CONVERSATION ON"]
    for label, value in fields:
        lines += [f"{label}:", value]
    return "\n".join(lines)


def turn_prompt(history: list[tuple[str, str]], message: str, exercise: str | None = None) -> str:
    """Return the prompt of one reply: the exercise, the recent conversation and the message."""
    lines = [exercise, ""] if exercise else []
    lines.append("CONVERSATION SO FAR")
    if history:
        lines += [f"{'Student' if role == 'student' else 'Assistant'}: {text}" for role, text in history]
    else:
        lines.append("(this is the first message)")
    lines += ["", "THE STUDENT'S MESSAGE", message, "", "Answer only with what you would tell the student."]
    return "\n".join(lines)


def blocked_reply() -> str:
    """Return the fixed answer to a message the guardrail refused."""
    return "I can't help with that message. If you have a question about the subject, tell me and we'll look at it."
