"""The tutor's own index of settings, resolved on every read.

The annotations below are the readable index, exactly as `variatio.config`'s are; the values
are declared in `tutor/settings.py` and derived here.
"""

from variatio import config as pipeline_config
from variatio import settings

REPLY_MODEL: str
CLASSIFY_MODEL: str
CRITERIA_MODEL: str
THINK_REPLY: bool | str
THINK_CRITERIA: bool | str
MESSAGE_MAX_CHARS: int
DAILY_MESSAGES: int | None
HISTORY_TURNS: int
REPLY_MAX_TOKENS: int
MAX_QUESTIONS: int
MAX_CODE_LINES: int
COPY_MAX_WORDS: int
PASSAGES_TOP_K: int
PASSAGE_THRESHOLD: float
PASSAGE_CHARS: int
ANCHORS_PER_CONCEPT: int
BANK_MATCH_THRESHOLD: float
FOCUS_THRESHOLD: float
FOCUS_MARGIN: float
CRITERIA_MAX_CHARS: int
CRITERIA_EVIDENCE_CHARS: int
CRITERIA_SOLUTIONS: int
CRITERIA_PER_UNIT: int
CRITERIA_MAX_TOKENS: int


def derive(values: dict[str, object]) -> dict[str, object]:
    """Compute the tutor's resolved values from the registry's."""
    # An empty model is the writer of a generation, which every installation already has
    # loaded, capped and protected; the two other calls follow the reply's.
    reply = str(values.get("tutor.models.reply") or "") or pipeline_config.VARIANT_GENERATION_LLM
    return {
        "REPLY_MODEL": reply,
        "CLASSIFY_MODEL": str(values.get("tutor.models.classify") or "") or reply,
        "CRITERIA_MODEL": str(values.get("tutor.models.criteria") or "") or reply,
        "THINK_REPLY": _think(values, "reply"),
        "THINK_CRITERIA": _think(values, "criteria"),
        "MESSAGE_MAX_CHARS": values["tutor.message_max_chars"],
        "DAILY_MESSAGES": values["tutor.daily_messages"],
        "HISTORY_TURNS": values["tutor.history_turns"],
        "REPLY_MAX_TOKENS": values["tutor.reply_max_tokens"],
        "MAX_QUESTIONS": values["tutor.max_questions"],
        "MAX_CODE_LINES": values["tutor.max_code_lines"],
        "COPY_MAX_WORDS": values["tutor.copy_max_words"],
        "PASSAGES_TOP_K": values["tutor.passages_top_k"],
        "PASSAGE_THRESHOLD": values["tutor.passage_threshold"],
        "PASSAGE_CHARS": values["tutor.passage_chars"],
        "ANCHORS_PER_CONCEPT": values["tutor.anchors_per_concept"],
        "BANK_MATCH_THRESHOLD": values["tutor.bank_match_threshold"],
        "FOCUS_THRESHOLD": values["tutor.focus_threshold"],
        "FOCUS_MARGIN": values["tutor.focus_margin"],
        "CRITERIA_MAX_CHARS": values["tutor.criteria_max_chars"],
        "CRITERIA_EVIDENCE_CHARS": values["tutor.criteria_evidence_chars"],
        "CRITERIA_SOLUTIONS": values["tutor.criteria_solutions"],
        "CRITERIA_PER_UNIT": values["tutor.criteria_per_unit"],
        "CRITERIA_MAX_TOKENS": values["tutor.criteria_max_tokens"],
    }


def _think(values: dict[str, object], phase: str) -> bool | str:
    """Return `False` or the effort level, as `variatio.settings.derived` does for its phases."""
    return values[f"tutor.effort.{phase}"] if values[f"tutor.reasoning.{phase}"] else False


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
