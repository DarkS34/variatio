"""The free chat's prompts in Spanish."""

from variatio.prompts.es import conversation as shared


def system_prompt(subject: str, language: str, code: bool) -> str:
    """Return the chat's standing instructions over the blocks every chat-like consumer shares.

    No method: it explains, solves and writes code as the student asks (the user's decision,
    2026-10-14). What it refuses, it refuses in one sentence and goes on helping. Since
    2026-11-02 it answers in the subject's language, as the tutor does (plan §12).
    """
    role = (
        "Eres el asistente de una asignatura. Ayudas a un alumno con lo que te pida sobre la "
        "asignatura o sobre cómo estudiarla: explicas conceptos, resuelves ejercicios paso a "
        "paso, propones ejemplos y prácticas, y corriges lo que el alumno haya hecho."
    )
    method = (
        "CÓMO AYUDAS\n"
        "- Contesta con claridad y sin rodeos. Cuando resuelvas algo, explica los pasos.\n"
        "- Si no estás seguro de un dato, dilo. No inventes datos, fuentes ni reglas "
        "mnemotécnicas, y no des por bueno un intento que tiene un error."
    )
    return shared.system_prompt(role, method, subject=subject, language=language, code=code)


def exercise_block(fields: list[tuple[str, str]]) -> str:
    """Render the exercise the conversation was opened on, with the fields the student reads."""
    lines = ["EJERCICIO SOBRE EL QUE EL ALUMNO ABRIÓ LA CONVERSACIÓN"]
    for label, value in fields:
        lines += [f"{label}:", value]
    return "\n".join(lines)


def turn_prompt(history: list[tuple[str, str]], message: str, exercise: str | None = None) -> str:
    """Return the prompt of one reply: the exercise, the recent conversation and the message."""
    lines = [exercise, ""] if exercise else []
    lines.append("CONVERSACIÓN HASTA AHORA")
    if history:
        lines += [f"{'Alumno' if role == 'student' else 'Asistente'}: {text}" for role, text in history]
    else:
        lines.append("(es el primer mensaje)")
    lines += ["", "MENSAJE DEL ALUMNO", message, "", "Responde solo con lo que le dirías al alumno."]
    return "\n".join(lines)


def blocked_reply() -> str:
    """Return the fixed answer to a message the guardrail refused."""
    return (
        "No puedo ayudarte con ese mensaje. Si tienes una duda de la asignatura, cuéntamela y la "
        "vemos."
    )
