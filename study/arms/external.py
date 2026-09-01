"""The commercial provider, confined to this file.

It is NOT registered in `inference._ENGINES`, and that is the line that does not get
crossed: `INFERENCE_ENGINE` picks the engine of the *pipeline*, and putting a closed
endpoint there would turn the project's "open-source only" decision into a config flag.
The evaluation is allowed to call one because measuring a commercial baseline is the
whole point of the naive arm.

`httpx` straight, no SDK — it is already a runtime dependency, so this adds none.

There are no retries: a silent second attempt at the SAME provider falsifies the per-arm
timing and can double a free quota. What there is instead is a CHAIN — a provider that did
not answer hands over to the next one — and `generate()` returns WHO answered, so a session
that fell back is filed under the provider that actually produced the item. A spent quota is
deliberately not remembered across sessions: every session starts at the head of the chain,
so the preferred provider comes back on its own when its window resets.
"""

from dataclasses import dataclass

import httpx
from loguru import logger

from variatio import config

from .. import ArmUnavailable
from .. import config as study_config

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


@dataclass(frozen=True)
class ExternalAnswer:
    """What came back, and from whom — never from whom it was asked for first."""

    text: str
    provider: str
    model: str


def _model(provider: str) -> str:
    """Return the model id configured for this provider, or an empty string."""
    return study_config.PROVIDER_MODELS.get(provider, "")


def _key(provider: str) -> str:
    """Return the API key configured for this provider, or an empty string."""
    return study_config.PROVIDER_KEYS.get(provider, "")


def configured_providers() -> list[str]:
    """The chain, in order, minus the unknown names and the ones with no key."""
    return [p for p in study_config.EXTERNAL_PROVIDERS if p in _CALLERS and _key(p)]


def is_configured() -> bool:
    """Say whether the commercial arm can be attempted at all."""
    return bool(configured_providers())


def primary() -> tuple[str, str]:
    """Who the arm tries first — or, with nothing usable, who it was asked to try."""
    chain = configured_providers() or study_config.EXTERNAL_PROVIDERS
    if not chain:
        return "none", ""
    return chain[0], _model(chain[0])


def unavailable_reason() -> str | None:
    """Say in words why nothing in the chain can be called, or None if something can.

    One usable provider is enough, so an unknown name is only worth reporting when it is
    the reason nothing at all is callable.
    """
    declared = study_config.EXTERNAL_PROVIDERS
    if not declared:
        return "El proveedor externo está desactivado (EVAL_EXTERNAL_PROVIDER=none)."
    if configured_providers():
        return None
    unknown = [p for p in declared if p not in _CALLERS]
    if unknown:
        return (
            f"Proveedor externo desconocido: {', '.join(unknown)} "
            f"(se esperaba {', '.join(_CALLERS)} o none)."
        )
    return (
        "No hay clave para ningún proveedor externo: define "
        + " o ".join(f"EVAL_{p.upper()}_API_KEY" for p in declared)
        + " en el fichero .env de la raíz del proyecto o en el entorno."
    )


def generate(prompt: str) -> ExternalAnswer:
    """Walk the chain until one provider answers, raising ArmUnavailable if none does.

    Every failure means the same thing — no item came back — so all of them hand over to
    the next provider, the 200 with no candidates that a safety filter produces included.

    NO SCHEMA CROSSES THIS BOUNDARY, and the signature is where that is enforced: there is
    no parameter to pass one through. The arm this serves is «the prompt somebody would
    type in a hurry», and nobody typing into a chat box attaches a JSON Schema to it — a
    machine-enforced grammar made the baseline decode better than the thing it is a
    baseline for, which flatters the system under test.
    """
    reason = unavailable_reason()
    if reason:
        raise ArmUnavailable(reason)

    failures: list[str] = []
    for provider in configured_providers():
        model = _model(provider)
        logger.info(f"Llamando al proveedor externo '{provider}' con '{model}'")
        try:
            text = _CALLERS[provider](prompt, model, _key(provider))
            if failures:
                logger.warning(
                    f"Se recurrió a '{provider}' tras {len(failures)} fallo(s) de otros proveedores"
                )
            return ExternalAnswer(text=text, provider=provider, model=model)
        except httpx.HTTPStatusError as e:
            failure = _http_reason(provider, e)
        except httpx.RequestError as e:
            failure = f"No se pudo contactar con {provider}: {e}"
        except (KeyError, IndexError, ValueError) as e:
            failure = f"Respuesta ininteligible de {provider}: {e}"
        logger.warning(f"Falló el proveedor externo '{provider}': {failure}")
        failures.append(failure)

    raise ArmUnavailable(" | ".join(failures))


def _gemini(prompt: str, model: str, key: str) -> str:
    """Call Gemini with the prompt and nothing else.

    Neither `responseSchema` nor `responseMimeType` goes out. The shape of the answer is
    asked for in the prose of the prompt, the way a person asks for it, and what arrives
    is read by `parse_with_repair` like any other arm's. The temperature is the one thing
    still sent, and it is the same number the local arms use, so the sampler is not a
    loose variable between the three.
    """
    generation_config = {"temperature": config.TEMPERATURE_GENERATION}
    response = httpx.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        },
        timeout=study_config.EXTERNAL_TIMEOUT,
    )
    response.raise_for_status()
    candidates = response.json().get("candidates") or []
    if not candidates:
        raise ValueError("la respuesta no traía ningún candidato (¿filtro de seguridad?)")
    parts = candidates[0].get("content", {}).get("parts") or []
    return "".join(part.get("text", "") for part in parts)


def _groq(prompt: str, model: str, key: str) -> str:
    """Call Groq's endpoint with no `response_format`, at the local arms' temperature.

    The rule is the chain's and not Gemini's: a fallback that constrained the decoder
    would smuggle back in, through the second provider, exactly what the first one stopped
    sending — and the session would be filed under whichever one happened to answer.
    """
    response = httpx.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config.TEMPERATURE_GENERATION,
        },
        timeout=study_config.EXTERNAL_TIMEOUT,
    )
    response.raise_for_status()
    choices = response.json().get("choices") or []
    if not choices:
        raise ValueError("la respuesta no traía ninguna opción")
    return choices[0].get("message", {}).get("content") or ""


def _http_reason(provider: str, error: httpx.HTTPStatusError) -> str:
    """Turn an HTTP failure into a sentence, naming the spent quota rather than a bare 429."""
    status = error.response.status_code
    if status == 429:
        return f"{provider} ha agotado la cuota gratuita (429). Reintenta más tarde."
    if status in (401, 403):
        return f"{provider} ha rechazado la clave API ({status})."
    detail = (error.response.text or "")[:200]
    return f"{provider} respondió {status}: {detail}"


# Which names are callable at all; the ORDER of the attempts is
# `study_config.EXTERNAL_PROVIDERS`, never this. Declared after the callers it names.
_CALLERS = {"gemini": _gemini, "groq": _groq}
