"""The commercial provider, confined to this file.

It is NOT registered in `inference._ENGINES`, and that is the line that does not get
crossed: `INFERENCE_ENGINE` picks the engine of the *pipeline*, and putting a closed
endpoint there would turn the project's "open-source only" decision into a config flag.
The evaluation is allowed to call one because measuring a commercial baseline is the
whole point of the naive arm.

`httpx` straight, no SDK — it is already a runtime dependency, so this adds none.
No retries: a silent retry falsifies the per-arm timing and can double a free quota.
"""

import httpx
from loguru import logger

from .. import config
from . import ArmUnavailable

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def is_configured() -> bool:
    return bool(config.EVAL_EXTERNAL_API_KEY) and config.EVAL_EXTERNAL_PROVIDER in ("gemini", "groq")


def unavailable_reason() -> str | None:
    provider = config.EVAL_EXTERNAL_PROVIDER
    if provider == "none":
        return "El proveedor externo está desactivado (EVAL_EXTERNAL_PROVIDER=none)."
    if provider not in ("gemini", "groq"):
        return f"Proveedor externo desconocido: '{provider}' (se esperaba gemini, groq o none)."
    if not config.EVAL_EXTERNAL_API_KEY:
        return (
            "No hay clave para el proveedor externo: define EVAL_EXTERNAL_API_KEY "
            "en el fichero .env de la raíz del proyecto o en el entorno."
        )
    return None


def generate(prompt: str) -> str:
    reason = unavailable_reason()
    if reason:
        raise ArmUnavailable(reason)

    provider = config.EVAL_EXTERNAL_PROVIDER
    model = config.EVAL_EXTERNAL_MODEL_ID
    logger.info(f"Calling external provider '{provider}' with model '{model}'")
    try:
        if provider == "gemini":
            return _gemini(prompt, model)
        return _groq(prompt, model)
    except httpx.HTTPStatusError as e:
        raise ArmUnavailable(_http_reason(provider, e)) from e
    except httpx.RequestError as e:
        raise ArmUnavailable(f"No se pudo contactar con {provider}: {e}") from e
    except (KeyError, IndexError, ValueError) as e:
        raise ArmUnavailable(f"Respuesta ininteligible de {provider}: {e}") from e


def _gemini(prompt: str, model: str) -> str:
    response = httpx.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": config.EVAL_EXTERNAL_API_KEY},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=config.EVAL_EXTERNAL_TIMEOUT,
    )
    response.raise_for_status()
    candidates = response.json().get("candidates") or []
    if not candidates:
        raise ValueError("la respuesta no traía ningún candidato (¿filtro de seguridad?)")
    parts = candidates[0].get("content", {}).get("parts") or []
    return "".join(part.get("text", "") for part in parts)


def _groq(prompt: str, model: str) -> str:
    response = httpx.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {config.EVAL_EXTERNAL_API_KEY}"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}]},
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
