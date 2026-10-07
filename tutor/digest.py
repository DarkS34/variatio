"""What a class asked the tutor in one week, in the model's words: a few themes per concept.

The teachers read it in «Clase → Actividad» (`server/activity.py`). The code groups the week's
messages by the concept their reply stood on, leaves out what is not about the subject, keeps
the most asked concepts and each one's latest messages, and asks the model, one call per
concept, for at most `MAX_THEMES` themes: one plain sentence each about what the students do
not understand, get wrong or ask for, with the numbers of the messages it covers. The model
never counts and never sees a name: the code counts a theme's messages and students from its
references.

PARAPHRASE ONLY (the user's decision, 2026-10-07). A theme that copies more than
`COPY_MAX_WORDS` running words of one of its messages, that names a student of the subject,
that is longer than `THEME_MAX_WORDS` or that covers no message is asked again once, with a
note naming what was wrong; a second failure drops that theme, never the call.
"""

import re
from dataclasses import dataclass

from loguru import logger

from variatio.core import inference
from variatio.core.lexicon import fold

from .calls import ask_object
from .checks import longest_shared_run

MAX_THEMES = 3
THEME_MAX_WORDS = 20
COPY_MAX_WORDS = 8
# Each message is clipped for the prompt: a pasted program says nothing more after this.
MESSAGE_CHARS = 600
# A part of a name shorter than this is not looked for alone: too many words are three letters.
NAME_PART_MIN = 4

SCHEMA = {
    "type": "object",
    "properties": {
        "themes": {
            "type": "array",
            "maxItems": MAX_THEMES,
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "messages": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["text", "messages"],
            },
        }
    },
    "required": ["themes"],
}

_WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class Asked:
    """One message of a group: its text, and where it lives (author, conversation, turn)."""

    text: str
    ref: tuple[int, str, int]


def summarise(
    concept: str,
    unit: str | None,
    asked: list[Asked],
    *,
    names: list[str],
    model: str,
    think: bool | str,
    tutor_prompts,
    prompts,
) -> list[dict]:
    """Return one concept's themes, each `{"text", "refs"}`; an empty list when none survives."""
    texts = [item.text.strip()[:MESSAGE_CHARS] for item in asked]
    prompt = tutor_prompts.digest_prompt(concept, unit, texts, MAX_THEMES, THEME_MAX_WORDS)
    kept: list[dict] = []
    note = ""
    for _ in range(2):
        try:
            answer = ask_object(
                prompt + note,
                SCHEMA,
                model=model,
                think=think,
                phase="tutor_digest",
                tutor_prompts=tutor_prompts,
                prompts=prompts,
                max_output_tokens=1024,
            )
        except inference.InferenceError as exc:
            logger.warning(f"[tutor] La síntesis de un concepto no se pudo escribir: {exc}")
            return kept
        good, failures = clean_themes(answer, asked, names)
        kept = good
        if not failures:
            return kept
        note = tutor_prompts.digest_retry_note(failures)
    logger.info(f"[tutor] La síntesis de un concepto deja fuera {len(failures)} tema(s) no válidos")
    return kept


def clean_themes(
    answer: dict | None, asked: list[Asked], names: list[str]
) -> tuple[list[dict], list[str]]:
    """Keep the themes that pass the checks, and name the failures of those that do not."""
    themes = (answer or {}).get("themes") if isinstance(answer, dict) else None
    kept: list[dict] = []
    failures: list[str] = []
    for theme in themes if isinstance(themes, list) else []:
        if not isinstance(theme, dict):
            continue
        text = " ".join(str(theme.get("text") or "").split()).strip(" \"'«»“”")
        numbers = [
            n for n in theme.get("messages") or [] if isinstance(n, int) and 1 <= n <= len(asked)
        ]
        covered = [asked[n - 1] for n in dict.fromkeys(numbers)]
        failure = _failure(text, covered, names)
        if failure:
            failures.append(failure)
            continue
        kept.append({"text": text, "refs": [list(item.ref) for item in covered]})
    return kept[:MAX_THEMES], failures


def _failure(text: str, covered: list[Asked], names: list[str]) -> str | None:
    """Return why a theme cannot be shown to a teacher, or None when it can."""
    if not text or not covered:
        return "empty"
    if len(_WORD.findall(text)) > THEME_MAX_WORDS:
        return "long"
    if any(longest_shared_run(text, item.text) > COPY_MAX_WORDS for item in covered):
        return "copy"
    if names_someone(text, names):
        return "name"
    return None


def names_someone(text: str, names: list[str]) -> bool:
    """Say whether a text names one of these people: a whole name, a username or a long part."""
    words = f" {' '.join(_WORD.findall(fold(text)))} "
    for name in names:
        parts = _WORD.findall(fold(name))
        if not parts:
            continue
        wanted = [" ".join(parts), *(part for part in parts if len(part) >= NAME_PART_MIN)]
        if any(f" {part} " in words for part in wanted):
            return True
    return False
