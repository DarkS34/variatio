import re
from dataclasses import dataclass

from loguru import logger

from . import config
from .core import inference, progress
from .core.inference import InferenceError

_SCORE = re.compile(r"<score>\s*(yes|no)\s*</score>", re.IGNORECASE)
_BARE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)

_LABELS = {
    "harm": "contenido dañino",
    "jailbreak": "un intento de saltarse las instrucciones del sistema",
    "social_bias": "sesgo contra un colectivo",
    "violence": "violencia",
    "profanity": "lenguaje ofensivo",
    "sexual_content": "contenido sexual",
    "unethical_behavior": "comportamiento poco ético",
}


@dataclass(frozen=True)
class Verdict:
    blocked_by: str | None
    checked: bool

    @property
    def blocked(self) -> bool:
        return self.blocked_by is not None

    @property
    def reason(self) -> str:
        if self.blocked_by is None:
            return ""
        return _LABELS.get(self.blocked_by, self.blocked_by)


def check(text: str, criteria: tuple[str, ...] = config.GUARDRAIL_CRITERIA) -> Verdict:
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

    verdict = Verdict(blocked_by=blocked_by, checked=not unreadable)
    if unreadable:
        logger.warning(
            f"El filtro no pudo juzgar {', '.join(unreadable)}; se deja pasar la petición"
        )
    progress.emit(
        "guardrail",
        ok=not verdict.blocked,
        criteria=verdict.blocked_by,
        checked=verdict.checked,
    )
    return verdict


def _score(text: str, criterion: str) -> bool | None:
    try:
        response = inference.generate(
            model=config.GUARDRAIL_LLM,
            prompt=text,
            system=criterion,
            think=False,
            temperature=config.TEMPERATURE_DETERMINISTIC,
        )
    except InferenceError as e:
        logger.warning(f"Falló la llamada del filtro para «{criterion}»: {e}")
        return None

    answer = (response.response or "").strip()
    match = _SCORE.search(answer) or _BARE.search(answer)
    if match is None:
        logger.warning(f"El filtro no dio un veredicto legible para «{criterion}»: {answer[:120]!r}")
        return None
    return match.group(1).lower() == "yes"
