import json
import time

import httpx
from loguru import logger

from .. import config
from . import progress
from .inference import GenerationResponse, InferenceError, OllamaEngine, TokenSink, split_thinking

STRICT_SCHEMA_MAX_CHARS = 5000

_UNSUPPORTED_KEYWORDS = ("pattern", "format", "minItems", "maxItems", "minLength", "maxLength")
_SUBSCHEMA_KEYS = ("items", "prefixItems", "anyOf", "allOf", "oneOf", "additionalProperties")
_SCHEMA_MAPS = ("properties", "$defs", "definitions")
_VISION_PREFIXES = ("gemma-4",)
_RETRY_STATUSES = (429, 503)
_MAX_ATTEMPTS = 5
_CATALOG_TTL_SECONDS = 300.0


# Cerebras' strict mode refuses the keywords Ollama's grammar simply ignores, and demands
# `additionalProperties: false` on every object. The transform is lossy on purpose: what a
# dropped `pattern` or `maxItems` used to guarantee is exactly what `parse_with_repair` and
# each component's own parser already re-check.
def strict_schema(schema: dict) -> dict:
    return _walk(schema)


def _walk(node: object) -> object:
    if isinstance(node, list):
        return [_walk(part) for part in node]
    if not isinstance(node, dict):
        return node
    out: dict = {}
    for key, value in node.items():
        if key in _UNSUPPORTED_KEYWORDS:
            continue
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            out[key] = {name: _walk(sub) for name, sub in value.items()}
        elif key in _SUBSCHEMA_KEYS:
            out[key] = _walk(value)
        else:
            out[key] = value
    if out.get("type") == "object" or "properties" in out:
        out["additionalProperties"] = False
    return out


def response_format(format: dict | str | None) -> dict | None:
    if format is None:
        return None
    if isinstance(format, str):
        return {"type": "json_object"}
    adapted = strict_schema(format)
    compact = json.dumps(adapted, ensure_ascii=False, separators=(",", ":"))
    strict = len(compact) <= STRICT_SCHEMA_MAX_CHARS
    if not strict:
        logger.warning(
            f"[cerebras] El esquema mide {len(compact)} caracteres (límite del modo "
            f"estricto: {STRICT_SCHEMA_MAX_CHARS}); se pide sin 'strict'"
        )
    return {
        "type": "json_schema",
        "json_schema": {"name": "respuesta", "strict": strict, "schema": adapted},
    }


# The same last-hop translation `OllamaEngine._think_option` does, in Cerebras' dialect:
# `reasoning_effort` takes "none"/"low"/"medium"/"high", with "none" as gemma-4's default.
# Cerebras has no "max", so the one level Ollama has above "high" maps down to it.
def reasoning_effort(think: bool | None) -> str | None:
    if think is None:
        return None
    if think is False:
        return "none"
    effort = str(config.THINK_EFFORT)
    return "high" if effort == "max" else effort


class CerebrasEngine:
    name = "cerebras"

    def __init__(self):
        self._client = httpx.Client(
            base_url=config.CEREBRAS_BASE_URL,
            headers={"Authorization": f"Bearer {config.CEREBRAS_API_KEY}"},
            timeout=httpx.Timeout(600.0, connect=10.0),
        )
        self._catalog: tuple[float, list[str]] | None = None

    def is_available(self) -> bool:
        try:
            return self._client.get("/models", timeout=5.0).status_code == 200
        except httpx.HTTPError:
            return False

    def catalog(self) -> list[str]:
        cached = self._catalog
        if cached is not None and time.monotonic() - cached[0] < _CATALOG_TTL_SECONDS:
            return cached[1]
        try:
            response = self._client.get("/models", timeout=10.0)
        except httpx.HTTPError as e:
            raise InferenceError(f"No se pudo leer el catálogo de Cerebras: {e}") from e
        if response.status_code != 200:
            raise InferenceError(
                f"Cerebras respondió {response.status_code} al listar sus modelos: "
                f"{response.text[:200]}"
            )
        models = sorted(str(row.get("id", "")) for row in response.json().get("data", []))
        models = [model for model in models if model]
        self._catalog = (time.monotonic(), models)
        return models

    def supports_thinking(self, model: str) -> bool:
        return True

    def supports_vision(self, model: str) -> bool:
        return model.startswith(_VISION_PREFIXES)

    def capabilities(self, model: str) -> list[str]:
        return ["thinking", *(["vision"] if self.supports_vision(model) else [])]

    def generate(
        self,
        model: str,
        prompt: str,
        think: bool | None = None,
        system: str | None = None,
        images: list[str] | None = None,
        temperature: float | None = None,
        format: dict | str | None = None,
    ) -> GenerationResponse:
        body = self._body(model, prompt, think, system, images, temperature, format)
        data = self._post(model, body).json()
        message = (data.get("choices") or [{}])[0].get("message") or {}
        reasoning = message.get("reasoning") or message.get("reasoning_content")
        return split_thinking(message.get("content") or "", reasoning)

    def generate_stream(
        self,
        model: str,
        prompt: str,
        think: bool | None = None,
        on_token: TokenSink | None = None,
        temperature: float | None = None,
    ) -> GenerationResponse:
        if on_token is None:
            return self.generate(model=model, prompt=prompt, think=think, temperature=temperature)

        body = self._body(model, prompt, think, None, None, temperature, None)
        body["stream"] = True
        answer: list[str] = []
        thinking: list[str] = []
        try:
            with self._client.stream("POST", "/chat/completions", json=body) as response:
                if response.status_code != 200:
                    response.read()
                    raise InferenceError(
                        f"Cerebras respondió {response.status_code} para '{model}': "
                        f"{response.text[:300]}"
                    )
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[len("data: ") :].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    delta = (json.loads(payload).get("choices") or [{}])[0].get("delta") or {}
                    thought = delta.get("reasoning") or delta.get("reasoning_content")
                    if thought:
                        thinking.append(thought)
                        on_token(thought, "thinking")
                    text = delta.get("content")
                    if text:
                        answer.append(text)
                        on_token(text, "answer")
                    progress.checkpoint()
        except httpx.HTTPError as e:
            raise InferenceError(f"Cerebras generation failed for model '{model}': {e}") from e

        return GenerationResponse(
            response="".join(answer).strip(), thinking="".join(thinking).strip() or None
        )

    def embed(self, model: str, text: str) -> list[float]:
        raise InferenceError(
            f"'{model}' está enrutado a Cerebras, que aquí no sirve embeddings: "
            "el modelo de embedding debe quedar fuera de CEREBRAS_MODELS"
        )

    def embed_batch(self, model: str, texts: list[str]) -> list[list[float]]:
        raise InferenceError(
            f"'{model}' está enrutado a Cerebras, que aquí no sirve embeddings: "
            "el modelo de embedding debe quedar fuera de CEREBRAS_MODELS"
        )

    def _body(
        self,
        model: str,
        prompt: str,
        think: bool | None,
        system: str | None,
        images: list[str] | None,
        temperature: float | None,
        format: dict | str | None,
    ) -> dict:
        if images and not self.supports_vision(model):
            raise InferenceError(
                f"Model '{model}' has no vision capability, so it cannot read the "
                f"{len(images)} image(s) it was given"
            )
        content: object = prompt
        if images:
            content = [
                {"type": "text", "text": prompt},
                *(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image}"},
                    }
                    for image in images
                ),
            ]
        messages: list[dict] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})

        body: dict = {"model": model, "messages": messages}
        if temperature is not None:
            body["temperature"] = temperature
        effort = reasoning_effort(think)
        if effort is not None:
            body["reasoning_effort"] = effort
        shaped = response_format(format)
        if shaped is not None:
            body["response_format"] = shaped
        return body

    # 429 is business as usual on Cerebras' free tier (5 requests a minute), so it is
    # retried with the wait the server asks for; anything else non-200 is an answer, and
    # the daily token budget in particular comes back as an error worth reading, not
    # worth retrying.
    def _post(self, model: str, body: dict) -> httpx.Response:
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = self._client.post("/chat/completions", json=body)
            except httpx.HTTPError as e:
                raise InferenceError(f"Cerebras generation failed for model '{model}': {e}") from e
            if response.status_code in _RETRY_STATUSES and attempt < _MAX_ATTEMPTS:
                wait = _retry_wait(response, attempt)
                logger.warning(
                    f"[cerebras] {response.status_code} para '{model}'; "
                    f"reintento {attempt}/{_MAX_ATTEMPTS - 1} en {wait:.0f} s"
                )
                progress.checkpoint()
                time.sleep(wait)
                continue
            if response.status_code != 200:
                raise InferenceError(
                    f"Cerebras respondió {response.status_code} para '{model}': "
                    f"{response.text[:300]}"
                )
            return response
        raise InferenceError(f"Cerebras agotó los reintentos para '{model}'")


def _retry_wait(response: httpx.Response, attempt: int) -> float:
    try:
        wait = float(response.headers.get("retry-after", ""))
    except ValueError:
        wait = float(2**attempt)
    return min(max(wait, 1.0), 60.0)


# One engine, two backends: the models named in `CEREBRAS_MODELS` are served remotely and
# everything else — the guardrail and the embedder included — stays on Ollama. Residency,
# pulls, deletes and the idle release only ever mean the Ollama half, because remote
# weights have nothing to load or free.
class HybridEngine:
    name = "cerebras+ollama"

    def __init__(self):
        self._ollama = OllamaEngine()
        self._cerebras = CerebrasEngine()

    def _remote(self, model: str) -> bool:
        return model in config.CEREBRAS_MODELS

    def _backend(self, model: str):
        return self._cerebras if self._remote(model) else self._ollama

    # The health poll asks about the half this process must have to do anything at all;
    # a Cerebras outage surfaces as a readable error on the first remote call instead of
    # costing every open tab a transatlantic round trip each 15 s.
    def is_available(self) -> bool:
        return self._ollama.is_available()

    def remote_models(self) -> frozenset[str]:
        return frozenset(config.CEREBRAS_MODELS)

    def generate(self, model: str, prompt: str, **kwargs) -> GenerationResponse:
        return self._backend(model).generate(model=model, prompt=prompt, **kwargs)

    def generate_stream(self, model: str, prompt: str, **kwargs) -> GenerationResponse:
        return self._backend(model).generate_stream(model=model, prompt=prompt, **kwargs)

    def embed(self, model: str, text: str) -> list[float]:
        return self._backend(model).embed(model, text)

    def embed_batch(self, model: str, texts: list[str]) -> list[list[float]]:
        return self._backend(model).embed_batch(model, texts)

    def capabilities(self, model: str) -> list[str]:
        return self._backend(model).capabilities(model)

    def supports_thinking(self, model: str) -> bool:
        return self._backend(model).supports_thinking(model)

    def supports_vision(self, model: str) -> bool:
        return self._backend(model).supports_vision(model)

    def installed_models(self) -> list[str]:
        return [info["model"] for info in self.installed_models_detail()]

    # The remote half lists Cerebras' whole catalogue, so the panel can point a phase at
    # any of it; when the catalogue is unreachable the declared routing list stands in,
    # which keeps a required remote model from reading as «sin instalar» during a blip.
    def installed_models_detail(self) -> list[dict]:
        local = self._ollama.installed_models_detail()
        try:
            remote = self._cerebras.catalog()
        except InferenceError as e:
            logger.debug(f"[cerebras] Catálogo no disponible: {e}")
            remote = sorted(config.CEREBRAS_MODELS)
        return local + [{"model": model, "size": None, "remote": True} for model in remote]

    def running_models(self) -> list[dict]:
        return self._ollama.running_models()

    def unload(self, model: str, is_embedding: bool = False) -> bool:
        if self._remote(model):
            return True
        return self._ollama.unload(model, is_embedding=is_embedding)

    def unload_all(self) -> list[str]:
        return self._ollama.unload_all()

    def ensure_model(self, model: str) -> bool:
        if not self._remote(model):
            return self._ollama.ensure_model(model)
        try:
            catalog = self._cerebras.catalog()
        except InferenceError as e:
            logger.warning(f"[cerebras] No se pudo comprobar '{model}': {e}")
            return False
        if model not in catalog:
            logger.warning(f"[cerebras] '{model}' no está en el catálogo de Cerebras")
            return False
        return True

    def warmup(self, model: str, is_embedding: bool = False) -> None:
        if self._remote(model):
            return
        self._ollama.warmup(model, is_embedding=is_embedding)

    def pull(self, model: str, on_progress=None) -> None:
        if self._remote(model):
            raise InferenceError(f"'{model}' se sirve en Cerebras; no hay nada que descargar")
        self._ollama.pull(model, on_progress)

    def delete(self, model: str) -> None:
        if self._remote(model):
            raise InferenceError(f"'{model}' se sirve en Cerebras; no hay nada que borrar")
        self._ollama.delete(model)
