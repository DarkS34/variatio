"""The free chat's own index of settings, resolved on every read.

The annotations below are the readable index, as `variatio.config`'s are; the values are
declared in `apps/chat/settings.py` and derived here.
"""

from variatio import config as pipeline_config
from variatio import settings

REPLY_MODEL: str
THINK_REPLY: bool | str
MESSAGE_MAX_CHARS: int
DAILY_MESSAGES: int | None
HISTORY_TURNS: int
REPLY_MAX_TOKENS: int


def derive(values: dict[str, object]) -> dict[str, object]:
    """Compute the chat's resolved values from the registry's."""
    # An empty model is the writer of a generation, which every installation already has
    # loaded, capped and protected (the user's decision, 2026-10-14).
    reply = str(values.get("chat.models.reply") or "") or pipeline_config.VARIANT_GENERATION_LLM
    return {
        "REPLY_MODEL": reply,
        "THINK_REPLY": values["chat.effort.reply"] if values["chat.reasoning.reply"] else False,
        "MESSAGE_MAX_CHARS": values["chat.message_max_chars"],
        "DAILY_MESSAGES": values["chat.daily_messages"],
        "HISTORY_TURNS": values["chat.history_turns"],
        "REPLY_MAX_TOKENS": values["chat.reply_max_tokens"],
    }


def __getattr__(name: str):
    """Resolve one of the annotated names above, freshly, on every read.

    `settings.reload()` rewrites `variatio.config`'s globals through the namespace it was
    handed and this module is not that namespace, so caching here would serve the value the
    panel just replaced.
    """
    values = derive(settings.values())
    if name in values:
        return values[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
