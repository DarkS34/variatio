"""The commercial provider, confined to this file.

It is NOT registered in `inference._ENGINES`, and that is the line that does not get
crossed: `INFERENCE_ENGINE` picks the engine of the *pipeline*, and putting a closed
endpoint there would turn the project's "open-source only" decision into a config flag.
The evaluation is allowed to call one because measuring a commercial baseline is the
whole point of the naive arm.

`httpx` straight, no SDK — it is already a runtime dependency, so this adds none.

**Still no retries** — a silent second attempt at the *same* provider falsifies the per-arm
timing and can double a free quota — but `config.EVAL_EXTERNAL_PROVIDER` is a CHAIN, and a
provider that did not answer hands over to the next one. The failure this exists for is
Gemini's free tier returning 429 in the middle of a data-collection session: recording the
arm `unavailable` there measures Google's billing, not the commercial baseline.

What keeps the data honest is that `generate()` returns WHO answered. `ArmResult` records
the provider and model that actually produced the item instead of the one configured first,
so a session that fell back is visible in the reveal panel and in the CSV rather than being
filed under Gemini. The arm's `elapsed_ms` does include the failed attempt: it measures what
the commercial branch cost to answer, which is the honest reading of a fallback.

A spent quota is deliberately NOT remembered across sessions. Every session starts at the
head of the chain again, so the moment the quota window resets the preferred provider comes
back on its own — at the price of one fast 4xx while it is still spent.
"""

from dataclasses import dataclass

import httpx
from loguru import logger

from .. import config
from . import ArmUnavailable

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


@dataclass(frozen=True)
class ExternalAnswer:
    text: str
    provider: str
    model: str


def _model(provider: str) -> str:
    return config.EVAL_PROVIDER_MODELS.get(provider, "")


def _key(provider: str) -> str:
    return config.EVAL_PROVIDER_KEYS.get(provider, "")


def configured_providers() -> list[str]:
    """The chain, in order, minus the unknown names and the ones with no key."""
    return [p for p in config.EVAL_EXTERNAL_PROVIDERS if p in _CALLERS and _key(p)]


def is_configured() -> bool:
    return bool(configured_providers())


def primary() -> tuple[str, str]:
    """Who the arm tries first — or, with nothing usable, who it was asked to try."""
    chain = configured_providers() or config.EVAL_EXTERNAL_PROVIDERS
    if not chain:
        return "none", ""
    return chain[0], _model(chain[0])


# One usable provider is enough, so an unknown name in the chain is only worth a message
# when it is the reason nothing can be called at all.
def unavailable_reason() -> str | None:
    declared = config.EVAL_EXTERNAL_PROVIDERS
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


# Every branch here means the same thing — no item came back — so all three hand over to the
# next provider, including the 200 with no candidates that a safety filter produces. The
# distinction that would justify stopping (the provider *answered*, and said no) is not one
# this arm can act on: it would still have nothing to compare.
def generate(prompt: str, schema: dict | None = None) -> ExternalAnswer:
    reason = unavailable_reason()
    if reason:
        raise ArmUnavailable(reason)

    failures: list[str] = []
    for provider in configured_providers():
        model = _model(provider)
        logger.info(f"Calling external provider '{provider}' with model '{model}'")
        try:
            text = _CALLERS[provider](prompt, model, _key(provider), schema)
            if failures:
                logger.warning(
                    f"External arm fell back to '{provider}' after {len(failures)} failure(s)"
                )
            return ExternalAnswer(text=text, provider=provider, model=model)
        except httpx.HTTPStatusError as e:
            failure = _http_reason(provider, e)
        except httpx.RequestError as e:
            failure = f"No se pudo contactar con {provider}: {e}"
        except (KeyError, IndexError, ValueError) as e:
            failure = f"Respuesta ininteligible de {provider}: {e}"
        logger.warning(f"External provider '{provider}' failed: {failure}")
        failures.append(failure)

    raise ArmUnavailable(" | ".join(failures))


# The exemplars profile's own schema goes out UNTRANSLATED. Gemini documents an OpenAPI 3.0
# subset, so a converter looked necessary, but `gemini-3.6-flash` takes the Pydantic schema
# as it comes — `title`, `anyOf: [string, null]` and all — and answers with the exact keys.
# Writing one anyway was actively worse: it dropped `minLength`/`maximum`, which
# `_spec_to_field` does support, so this arm would have decoded under a WEAKER schema than
# the local two. Parity of parsing is the one thing the comparison must not lose.
def _gemini(prompt: str, model: str, key: str, schema: dict | None = None) -> str:
    generation_config = (
        {}
        if schema is None
        else {
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema,
            }
        }
    )
    response = httpx.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": key},
        json={"contents": [{"parts": [{"text": prompt}]}], **generation_config},
        timeout=config.EVAL_EXTERNAL_TIMEOUT,
    )
    response.raise_for_status()
    candidates = response.json().get("candidates") or []
    if not candidates:
        raise ValueError("la respuesta no traía ningún candidato (¿filtro de seguridad?)")
    parts = candidates[0].get("content", {}).get("parts") or []
    return "".join(part.get("text", "") for part in parts)


# Groq speaks OpenAI's `json_schema`, whose strict mode additionally demands
# `additionalProperties: false` on every object — the one thing Pydantic does not emit.
# This path is now the FALLBACK rather than an alternative nobody selects, so a 400 from
# here no longer waits for someone to switch providers by hand: it shows up appended to
# Gemini's own failure the first time Gemini's quota runs out. This is where to look.
def _openai_schema(schema: dict) -> dict:
    out = dict(schema)
    if "properties" in out:
        out["properties"] = {n: _openai_schema(s) for n, s in out["properties"].items()}
        out["additionalProperties"] = False
    if "items" in out:
        out["items"] = _openai_schema(out["items"])
    return out


def _groq(prompt: str, model: str, key: str, schema: dict | None = None) -> str:
    response_format = (
        {}
        if schema is None
        else {
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "item",
                    "schema": _openai_schema(schema),
                    "strict": True,
                },
            }
        }
    )
    response = httpx.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            **response_format,
        },
        timeout=config.EVAL_EXTERNAL_TIMEOUT,
    )
    response.raise_for_status()
    choices = response.json().get("choices") or []
    if not choices:
        raise ValueError("la respuesta no traía ninguna opción")
    return choices[0].get("message", {}).get("content") or ""


# A spent free quota is the failure this arm will actually hit during a data-collection
# session, so it gets said in words instead of arriving as a bare 429.
def _http_reason(provider: str, error: httpx.HTTPStatusError) -> str:
    status = error.response.status_code
    if status == 429:
        return f"{provider} ha agotado la cuota gratuita (429). Reintenta más tarde."
    if status in (401, 403):
        return f"{provider} ha rechazado la clave API ({status})."
    detail = (error.response.text or "")[:200]
    return f"{provider} respondió {status}: {detail}"


# Declared after the callers so the lookup can stay a plain dict. It says which names are
# callable at all; the ORDER of the attempts is `config.EVAL_EXTERNAL_PROVIDERS`, never this.
_CALLERS = {"gemini": _gemini, "groq": _groq}
