"""A conversation's title, written by the model once the conversation is about something.

A conversation starts titled by its first line, which is what the student typed and often
not what the conversation is about: «Hola», «no entiendo nada», a pasted statement. The
first reply that works on the subject — not a greeting, not a fixed answer — asks the
classification's model for a short title from the student's messages and the focus, and
the conversation keeps it. It is asked once: a title that changed under the student's eyes
would make the list hard to find things in.

A title is a convenience and never a reason to lose a reply: any failure leaves the title
the conversation already had.
"""

import re

from loguru import logger

from variatio.core import inference

from .calls import ask_object

# Enough for six words of any language; a longer answer is no title.
MAX_CHARS = 60
_MESSAGE_CHARS = 400
_MESSAGES = 3

_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
}


def name_conversation(
    messages: list[str], concepts: list[str], *, model: str, tutor_prompts, prompts
) -> str | None:
    """Return a title for a conversation from its first messages and focus, or None."""
    shown = [text.strip()[:_MESSAGE_CHARS] for text in messages if text.strip()][:_MESSAGES]
    try:
        answer = ask_object(
            tutor_prompts.title_prompt(shown, concepts),
            _SCHEMA,
            model=model,
            think=False,
            phase="tutor_classify",
            tutor_prompts=tutor_prompts,
            prompts=prompts,
            max_output_tokens=64,
        )
    except inference.InferenceError as exc:
        logger.warning(f"[tutor] No se pudo poner título a la conversación: {exc}")
        return None
    return clean((answer or {}).get("title"))


def clean(value) -> str | None:
    """Return a model's title without quotes, final stop or extra spaces, or None if unusable."""
    text = " ".join(str(value or "").split()).strip(" \"'«»“”.")
    if not text or len(text) > MAX_CHARS or re.search(r"[{}\[\]<>]", text):
        return None
    return text[0].upper() + text[1:]
