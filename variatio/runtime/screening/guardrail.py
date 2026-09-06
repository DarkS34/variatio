"""The safety screen over the commission's free text.

A regex catches prompt injection before any model is asked; the rest is one call per
criterion of `config.GUARDRAIL_CRITERIA`, stopping at the first that flags. A criterion
the model cannot answer is logged and skipped rather than blocking, but it clears
`checked` so the caller knows the screen was only partial.

The patterns and the wording of a verdict come from `wording`, not from this file: an
override is written in the workspace's own language, so a Spanish alternation over an
English commission recognises nothing but the English half both sets share.
"""

import re
from dataclasses import dataclass

from loguru import logger

from ... import config, wording as wording_sets
from ...core import inference, progress
from ...core.inference import InferenceError
from ...core.lexicon import fold

_SCORE = re.compile(r"<score>\s*(yes|no)\s*</score>", re.IGNORECASE)
_BARE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)

_INJECTION_CACHE: dict[str, re.Pattern[str]] = {}


def injection_pattern(wording) -> re.Pattern[str]:
    """Return the compiled override detector for one language, compiling it once.

    Two branches plus whatever the language adds: a verb reaching an object within 40
    characters, and an object carried by a backward-looking qualifier with no verb at all.
    """
    cached = _INJECTION_CACHE.get(wording.LANGUAGE)
    if cached is not None:
        return cached
    branches = [
        rf"\b(?:{wording.OVERRIDE_VERBS})\b[^.;:!?]{{0,40}}?\b(?:{wording.OVERRIDE_OBJECTS})\b",
        rf"\b(?:{wording.OVERRIDE_OBJECTS}) (?:{wording.OVERRIDE_QUALIFIERS})\b",
        *wording.INJECTION_PATTERNS,
    ]
    compiled = re.compile("|".join(branches))
    _INJECTION_CACHE[wording.LANGUAGE] = compiled
    return compiled


@dataclass(frozen=True)
class Verdict:
    """The screen's outcome; `checked` is false when a criterion could not be judged."""

    blocked_by: str | None
    checked: bool
    reason: str = ""

    @property
    def blocked(self) -> bool:
        """True when a criterion flagged the text."""
        return self.blocked_by is not None


def check(text: str, criteria: list[str] | None = None, wording=None) -> Verdict:
    """Screen one free text and return the verdict.

    The injection regex runs first, over the folded text and before any model call: an
    instruction aimed at the system needs no criterion to be recognised. The criteria are
    then evaluated in order and the first to flag stops the loop.

    `criteria` is resolved here and not in the signature: a default binds at import, so the
    setting could never follow what the panel saves. `None` is "whatever is configured now"
    and an empty list is an instruction, so the two are told apart with `is None`.
    """
    if criteria is None:
        criteria = config.GUARDRAIL_CRITERIA
    if wording is None:
        wording = wording_sets.of(None)

    def verdict_for(blocked_by: str | None, checked: bool) -> Verdict:
        label = wording.GUARDRAIL_LABELS.get(blocked_by, blocked_by) if blocked_by else ""
        return Verdict(blocked_by=blocked_by, checked=checked, reason=label)

    if injection_pattern(wording).search(fold(text)):
        verdict = verdict_for("instruction_override", True)
        progress.emit("guardrail", ok=False, criteria=verdict.blocked_by, checked=True)
        return verdict

    blocked_by: str | None = None
    unreadable: list[str] = []

    for criterion in criteria:
        progress.checkpoint()
        flagged = _score(text, criterion)
        if flagged is None:
            unreadable.append(criterion)
            continue
        if flagged:
            blocked_by = criterion
            break

    verdict = verdict_for(blocked_by, not unreadable)
    if unreadable:
        logger.warning(
            f"The guardrail could not judge {', '.join(unreadable)}; letting the request through"
        )
    progress.emit(
        "guardrail",
        ok=not verdict.blocked,
        criteria=verdict.blocked_by,
        checked=verdict.checked,
    )
    return verdict


def _score(text: str, criterion: str) -> bool | None:
    """Ask the guardrail model about one criterion; None when the answer is unreadable."""
    try:
        response = inference.generate(
            model=config.GUARDRAIL_LLM,
            prompt=text,
            system=criterion,
            think=False,
            temperature=config.TEMPERATURE_DETERMINISTIC,
        )
    except InferenceError as e:
        logger.warning(f"The guardrail call failed for «{criterion}»: {e}")
        return None

    answer = (response.response or "").strip()
    match = _SCORE.search(answer) or _BARE.search(answer)
    if match is None:
        logger.warning(f"The guardrail gave no readable verdict for «{criterion}»: {answer[:120]!r}")
        return None
    return match.group(1).lower() == "yes"
