import re
from dataclasses import dataclass

from loguru import logger

from . import config
from .core import inference, progress
from .core.inference import InferenceError
from .core.lexicon import fold

_SCORE = re.compile(r"<score>\s*(yes|no)\s*</score>", re.IGNORECASE)
_BARE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)

_OVERRIDE_VERBS = (
    r"olvida(?:te|d)?|olvides|ignora(?:d)?|ignores|omite|omitas|omitid|"
    r"descarta(?:d)?|descartes|obvia|obvies|anula(?:d)?|anules|salta(?:te)?|saltes|"
    r"incumple|desobedece|haz caso omiso|"
    r"no (?:sigas|obedezcas|cumplas|respetes|apliques|tengas en cuenta)|"
    r"deja de (?:seguir|obedecer|aplicar|hacer caso)|"
    r"forget|ignore|disregard|bypass|override|stop following|do not follow"
)
_OVERRIDE_OBJECTS = (
    r"instruccion(?:es)?|indicacion(?:es)?|regla(?:s)?|orden(?:es)?|consigna(?:s)?|"
    r"restriccion(?:es)?|directriz|directrices|prompt(?:s)?|"
    r"instruction(?:s)?|rule(?:s)?|constraint(?:s)?|directive(?:s)?|guideline(?:s)?"
)
_INJECTION = re.compile(
    rf"\b(?:{_OVERRIDE_VERBS})\b[^.;:!?]{{0,40}}?\b(?:{_OVERRIDE_OBJECTS})\b"
    rf"|\b(?:{_OVERRIDE_OBJECTS}) (?:anterior(?:es)?|previ[ao]s?|de arriba)\b"
    r"|\b(?:system|previous|prior) prompt\b"
    r"|\bprompt del sistema\b"
    r"|\binstrucciones del sistema\b(?! ?operativ)"
)

_LABELS = {
    "instruction_override": "una instrucción dirigida al sistema, no al ejercicio",
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
    if _INJECTION.search(fold(text)):
        verdict = Verdict(blocked_by="instruction_override", checked=True)
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

    verdict = Verdict(blocked_by=blocked_by, checked=not unreadable)
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
