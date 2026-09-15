"""The Cerebras backend, and the hybrid engine that routes some models to it.

Everything not named in `CEREBRAS_MODELS` — the guardrail and the embedder always included
— stays on Ollama, so residency, pulls, deletes and the idle release only ever mean the
local half.
"""

import hashlib
import json
import time

import httpx
from loguru import logger

from .. import config
from . import cerebras_budget, progress
from .inference import (
    DEFAULT_THINK_EFFORT,
    GenerationResponse,
    InferenceError,
    OllamaEngine,
    TokenSink,
    split_thinking,
)

STRICT_SCHEMA_MAX_CHARS = 5000
_WRAPPER_NAME = "lista"

_UNSUPPORTED_KEYWORDS = ("pattern", "format", "minItems", "maxItems", "minLength", "maxLength")
# Pydantic titles every field it writes and the decoder never reads them: metadata, never
# shape, and pure weight against the 5 000-character cap — one real extraction schema
# measured 5 001 characters with them and 4 502 without.
_NOISE_KEYWORDS = ("title",)
_DROPPED_KEYWORDS = _UNSUPPORTED_KEYWORDS + _NOISE_KEYWORDS
_SUBSCHEMA_KEYS = ("items", "prefixItems", "anyOf", "allOf", "oneOf", "additionalProperties")
_SCHEMA_MAPS = ("properties", "$defs", "definitions")
# Cerebras' catalogue lists image input for both families, ten per request; gpt-oss does
# not take images.
_VISION_PREFIXES = ("gemma-4", "qwen-3.8")
_RETRY_STATUSES = (429, 503)
_MAX_ATTEMPTS = 5
_CATALOG_TTL_SECONDS = 300.0
# How long a failed catalogue read stands before the next attempt: routing asks for the
# catalogue on every call, and a dead API must not cost every one of them a round trip.
_CATALOG_RETRY_SECONDS = 60.0


def strict_schema(schema: dict) -> dict:
    """Adapt a JSON Schema to what Cerebras' strict mode accepts.

    Strict mode refuses the keywords Ollama's grammar merely ignores — `pattern`,
    `format`, the four `min`/`max` bounds — refuses `const` outright, and demands
    `additionalProperties: false` on every object that does not declare one of its own.
    `const` is the one refusal with a lossless translation and is rewritten as an `enum` of
    one; dropping the rest is lossy on purpose, since what a `pattern` guaranteed is what
    `parse_with_repair` and each component's parser re-check anyway.

    An object that DOES declare an `additionalProperties` schema is an open-ended map and
    is left alone: closing it rewrites the value's own type as `false`, leaving an object
    that can hold no field at all, and Cerebras answers 400. Such a map costs strict mode
    itself — measured, a typed one is refused just the same — not its shape.
    """
    return _walk(schema)


def _walk(node: object) -> object:
    """Rewrite one schema node and everything nested inside it."""
    if isinstance(node, list):
        return [_walk(part) for part in node]
    if not isinstance(node, dict):
        return node
    out: dict = {}
    for key, value in node.items():
        if key in _DROPPED_KEYWORDS:
            continue
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            out[key] = {name: _walk(sub) for name, sub in value.items()}
        elif key in _SUBSCHEMA_KEYS:
            out[key] = _walk(value)
        elif key == "const":
            out["enum"] = [value]
        else:
            out[key] = value
    if "additionalProperties" in node:
        return out
    if out.get("type") == "object" or "properties" in out:
        out["additionalProperties"] = False
    return out


def _open_map(node: object) -> bool:
    """Whether any object in the schema takes keys the schema does not name.

    Strict mode refuses those, so a schema containing one is asked for without it.
    """
    if isinstance(node, list):
        return any(_open_map(part) for part in node)
    if not isinstance(node, dict):
        return False
    if node.get("type") == "object" and "properties" not in node and "anyOf" not in node:
        return True
    for key, value in node.items():
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            if any(_open_map(sub) for sub in value.values()):
                return True
        elif key in _SUBSCHEMA_KEYS and _open_map(value):
            return True
    return False


# A degradation is a property of the SCHEMA and not of the call, and the same schema goes
# out on every call of a phase and again on every repair: one bank build printed the size
# warning 29 times. A build has a process of its own, so once per process misses nothing.
_WARNED: set[str] = set()


class CerebrasEngine:
    """The remote half: Cerebras' OpenAI-compatible API, gated by the spending ledger."""

    name = "cerebras"

    def __init__(self):
        """Open the client with the configured base URL and key, and empty the catalogue."""
        self._client = httpx.Client(
            base_url=config.CEREBRAS_BASE_URL,
            headers={"Authorization": f"Bearer {config.CEREBRAS_API_KEY}"},
            timeout=httpx.Timeout(600.0, connect=10.0),
        )
        self._catalog: tuple[float, list[str]] | None = None
        self._catalog_failed_at: float | None = None

    def is_available(self) -> bool:
        """Whether the API answers at all."""
        try:
            return self._client.get("/models", timeout=5.0).status_code == 200
        except httpx.HTTPError:
            return False

    def known_models(self) -> frozenset[str]:
        """The catalogue as far as this process knows it, never raising.

        A fresh read when the cache has expired; the LAST read when the API does not
        answer, so a blip mid-build never reroutes a model to Ollama; an empty set when
        nothing was ever read. A failure is remembered for `_CATALOG_RETRY_SECONDS`.
        """
        failed = self._catalog_failed_at
        if failed is not None and time.monotonic() - failed < _CATALOG_RETRY_SECONDS:
            return frozenset(self._catalog[1]) if self._catalog else frozenset()
        try:
            return frozenset(self.catalog())
        except InferenceError as e:
            self._catalog_failed_at = time.monotonic()
            logger.debug(f"[cerebras] Catalogue unavailable, keeping what was read: {e}")
            return frozenset(self._catalog[1]) if self._catalog else frozenset()

    def catalog(self) -> list[str]:
        """The models Cerebras serves, cached for `_CATALOG_TTL_SECONDS`."""
        cached = self._catalog
        if cached is not None and time.monotonic() - cached[0] < _CATALOG_TTL_SECONDS:
            return cached[1]
        try:
            response = self._client.get("/models", timeout=10.0)
        except httpx.HTTPError as e:
            raise InferenceError(f"No se pudo leer el catálogo de Cerebras: {e}") from e
        if response.status_code != 200:
            # This message reaches the panel verbatim, and a reply from upstream is not
            # ours to reflect: the body stays in the log.
            logger.debug(f"[cerebras] Error body while listing models: {response.text[:300]}")
            raise InferenceError(
                f"Cerebras respondió {response.status_code} al listar sus modelos "
                f"({_endpoint_label('/models')}); el detalle está en el registro"
            )
        models = sorted(str(row.get("id", "")) for row in response.json().get("data", []))
        models = [model for model in models if model]
        self._catalog = (time.monotonic(), models)
        self._catalog_failed_at = None
        return models

    def supports_thinking(self, model: str) -> bool:
        """Every model Cerebras serves takes a `reasoning_effort`."""
        return True

    def capabilities(self, model: str) -> list[str]:
        """The same shape Ollama's capability list has, derived rather than asked for."""
        return ["thinking", *(["vision"] if self.supports_vision(model) else [])]

    def generate_stream(
        self,
        model: str,
        prompt: str,
        think: bool | str | None = None,
        on_token: TokenSink | None = None,
        temperature: float | None = None,
    ) -> GenerationResponse:
        """Stream one answer, feeding each token to `on_token` as it arrives.

        The claim IS the room: it is booked at the estimate before the call goes out, so a
        second job on the remote lane sees a smaller window rather than the same one.
        Releasing it at the end is a no-op once the call has been recorded — the room only
        comes back when the call never happened.
        """
        if on_token is None:
            return self.generate(model=model, prompt=prompt, think=think, temperature=temperature)

        body = self._body(model, prompt, think, None, None, temperature, None)
        body["stream"] = True
        # A streamed answer carries no `usage` unless it is asked for, and without it the
        # ledger would charge a whole generation zero tokens.
        body["stream_options"] = {"include_usage": True}

        ledger = cerebras_budget.shared()
        phase = progress.current_activity()
        claim = ledger.wait(model, cerebras_budget.estimate_tokens(prompt), phase)

        try:
            with self._client.stream("POST", "/chat/completions", json=body) as response:
                if response.status_code != 200:
                    response.read()
                    ledger.record(model, phase, 0, 0, response.headers, claim=claim)
                    raise InferenceError(
                        _remote_error(response.status_code, model, response.text)
                    )
                answer, thinking, prompt_tokens, completion_tokens = _consume_stream(
                    response, on_token
                )
                ledger.record(
                    model, phase, prompt_tokens, completion_tokens, response.headers, claim=claim
                )
        except httpx.HTTPError as e:
            raise InferenceError(f"Cerebras generation failed for model '{model}': {e}") from e
        finally:
            ledger.release(claim)

        return GenerationResponse(
            response=answer.strip(), thinking=thinking.strip() or None
        )

    def generate(
        self,
        model: str,
        prompt: str,
        think: bool | str | None = None,
        system: str | None = None,
        images: list[str] | None = None,
        temperature: float | None = None,
        format: dict | str | None = None,
        max_output_tokens: int | None = None,
    ) -> GenerationResponse:
        """Ask `model` for one answer, unwrapping it when the schema had to be wrapped.

        `finish_reason == "length"` is the API saying the answer hit `max_completion_tokens`;
        it travels as `truncated` so the caller can refuse a cut answer instead of keeping
        it as a short one.
        """
        body = self._body(
            model, prompt, think, system, images, temperature, format,
            max_output_tokens=max_output_tokens,
        )
        data = self._post(model, body).json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        reasoning = message.get("reasoning") or message.get("reasoning_content")
        content = message.get("content") or ""
        shaped = body.get("response_format") or {}
        if (shaped.get("json_schema") or {}).get("name") == _WRAPPER_NAME:
            content = _unwrap(content)
        return split_thinking(content, reasoning, choice.get("finish_reason") == "length")

    def _body(
        self,
        model: str,
        prompt: str,
        think: bool | str | None,
        system: str | None,
        images: list[str] | None,
        temperature: float | None,
        format: dict | str | None,
        max_output_tokens: int | None = None,
    ) -> dict:
        """Assemble the chat-completions request for one call.

        Images travel as base64 data URLs typed by their own first bytes — a scanned page is
        sent as JPEG — and a model that cannot read one is refused up front rather than
        answering emptily.
        """
        if images and not self.supports_vision(model):
            raise InferenceError(
                f"Model '{model}' has no vision capability, so it cannot read the "
                f"{len(images)} image(s) it was given"
            )
        content: object = prompt
        if images:
            # The pictures go BEFORE the text: Gemma 4's model card asks for image content
            # ahead of the prompt, and Qwen's own examples order the parts the same way.
            content = [
                *(
                    {"type": "image_url", "image_url": {"url": _data_url(image)}}
                    for image in images
                ),
                {"type": "text", "text": prompt},
            ]
        messages: list[dict] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})

        body: dict = {"model": model, "messages": messages}
        if temperature is not None:
            body["temperature"] = temperature
        if max_output_tokens is not None:
            body["max_completion_tokens"] = max_output_tokens
        effort = reasoning_effort(think)
        if effort is not None:
            body["reasoning_effort"] = effort
        shaped = response_format(format)
        if shaped is not None:
            body["response_format"] = shaped
        return body

    def supports_vision(self, model: str) -> bool:
        """Whether `model` belongs to one of the families that read images."""
        return model.startswith(_VISION_PREFIXES)

    def _post(self, model: str, body: dict) -> httpx.Response:
        """Send one request, retrying only the statuses that mean "ask again".

        A 429 is retried with the wait the server asks for; anything else non-200 is an
        answer, and the exhausted daily budget in particular is worth reading rather than
        repeating. The ledger in front of this makes a 429 the exception: what is left is
        the answer to somebody ELSE spending the same account's budget.
        """
        ledger = cerebras_budget.shared()
        phase = progress.current_activity()
        estimate = cerebras_budget.estimate_tokens(_prompt_text(body))
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            response = self._send(ledger, model, phase, estimate, body)
            if response.status_code in _RETRY_STATUSES and attempt < _MAX_ATTEMPTS:
                wait = _retry_wait(response, attempt)
                logger.warning(
                    f"[cerebras] {response.status_code} for '{model}'; "
                    f"retry {attempt}/{_MAX_ATTEMPTS - 1} in {wait:.0f} s"
                )
                _sleep(wait)
                continue
            if response.status_code != 200:
                raise InferenceError(_remote_error(response.status_code, model, response.text))
            return response
        raise InferenceError(f"Cerebras agotó los reintentos para '{model}'")

    def _send(self, ledger, model: str, phase: str | None, estimate: int, body: dict):
        """Book the room, make one call and charge it whatever it cost.

        Every response is recorded, a 429 included: it spent a request whether or not it
        produced an answer, and a ledger counting only successes would walk straight back
        into the limit it just hit.
        """
        claim = ledger.wait(model, estimate, phase)
        try:
            response = self._client.post("/chat/completions", json=body)
        except httpx.HTTPError as e:
            ledger.release(claim)
            raise InferenceError(f"Cerebras generation failed for model '{model}': {e}") from e
        prompt_tokens, completion_tokens = _usage(response)
        ledger.record(model, phase, prompt_tokens, completion_tokens, response.headers, claim=claim)
        return response

    def embed(self, model: str, text: str) -> list[float]:
        """Refuse: Cerebras serves no embeddings here."""
        raise InferenceError(
            f"'{model}' está enrutado a Cerebras, que aquí no sirve embeddings: "
            "el modelo de embedding debe quedar fuera de CEREBRAS_MODELS"
        )

    def embed_batch(self, model: str, texts: list[str]) -> list[list[float]]:
        """Refuse: Cerebras serves no embeddings here."""
        raise InferenceError(
            f"'{model}' está enrutado a Cerebras, que aquí no sirve embeddings: "
            "el modelo de embedding debe quedar fuera de CEREBRAS_MODELS"
        )


def _data_url(image: str) -> str:
    """Type a base64 picture by its own first bytes: `/9j/` is JPEG's FF D8 FF, all else PNG."""
    mime = "image/jpeg" if image.startswith("/9j/") else "image/png"
    return f"data:{mime};base64,{image}"


def _consume_stream(response: httpx.Response, on_token: TokenSink) -> tuple[str, str, int, int]:
    """Read one SSE stream to its end, returning the answer, the reasoning and the usage.

    Every chunk is a point where a cancellation can take effect.
    """
    answer: list[str] = []
    thinking: list[str] = []
    prompt_tokens = completion_tokens = 0
    for line in response.iter_lines():
        if not line.startswith("data: "):
            continue
        payload = line[len("data: ") :].strip()
        if not payload or payload == "[DONE]":
            continue
        chunk = json.loads(payload)
        usage = chunk.get("usage")
        if usage:
            prompt_tokens = int(usage.get("prompt_tokens") or 0)
            completion_tokens = int(usage.get("completion_tokens") or 0)
        delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
        thought = delta.get("reasoning") or delta.get("reasoning_content")
        if thought:
            thinking.append(thought)
            on_token(thought, "thinking")
        text = delta.get("content")
        if text:
            answer.append(text)
            on_token(text, "answer")
        progress.checkpoint()
    return "".join(answer), "".join(thinking), prompt_tokens, completion_tokens


def _remote_error(status: int, model: str, body: str) -> str:
    """Phrase a remote failure for the panel: the status and the endpoint, not the body.

    Same rule as `inference._upstream_error` — what a remote API answers is its text, not
    ours, and these messages travel to the panel as the job's failure.
    """
    logger.debug(f"[cerebras] Body of error {status} for '{model}': {body[:300]}")
    return (
        f"Cerebras respondió {status} para '{model}' "
        f"({_endpoint_label('/chat/completions')}); el detalle está en el registro"
    )


def _endpoint_label(path: str) -> str:
    """The full URL of `path`, for an error an operator has to act on."""
    return f"{str(config.CEREBRAS_BASE_URL).rstrip('/')}{path}"


def _unwrap(text: str) -> str:
    """Return the array inside a one-key wrapper object, or `text` unchanged."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(data, dict) and set(data) == {"items"}:
        return json.dumps(data["items"], ensure_ascii=False)
    return text


def reasoning_effort(think: bool | str | None) -> str | None:
    """Translate `think` into Cerebras' `reasoning_effort`, at the last hop before the call.

    The same translation `OllamaEngine._think_option` does, in the other dialect: the
    levels are "none"/"low"/"medium"/"high", Cerebras has no "max", so Ollama's top level
    maps down to "high". A string is a per-phase effort already resolved by
    `settings.derived` and travels untouched; `True` becomes `DEFAULT_THINK_EFFORT`.

    It assumes every routed model has an off switch. Some families answer 400 "Unsupported
    reasoning effort: none" and would need `False` floored at their own minimum; none is
    routed here today.
    """
    if think is None:
        return None
    if think is False:
        return "none"
    effort = think if isinstance(think, str) else DEFAULT_THINK_EFFORT
    return "high" if effort == "max" else effort


def response_format(format: dict | str | None) -> dict | None:
    """Build Cerebras' `response_format`, degrading where strict mode cannot hold.

    Strict mode demands an OBJECT at the root — an array root answers 400 "Extra top level
    keys found in JSON schema: {'items'}" — so an array schema is wrapped in a one-key
    object and `generate` unwraps the reply before any parser sees it. The wrapper's `name`
    is the marker, which is why `_WRAPPER_NAME` must never be the plain "respuesta".
    Wrapped implies strict: the wrap is only taken when the wrapper clears every other
    check, so a reply to a wrapped schema is decoder-guaranteed to be the object `_unwrap`
    expects.

    `strict` is dropped in three cases — a non-object root that cannot be wrapped, an
    open-keyed map, and a schema above `STRICT_SCHEMA_MAX_CHARS`. The shape still travels
    and still guides: measured, the same call answered arrays with the map typed and bare
    strings with it untyped. What is lost is the decoder's guarantee, which
    `parse_with_repair` takes over from there.
    """
    if format is None:
        return None
    if isinstance(format, str):
        return {"type": "json_object"}
    adapted = strict_schema(format)
    name = "respuesta"
    if adapted.get("type") != "object" and not _open_map(adapted):
        candidate = {
            "type": "object",
            "properties": {"items": adapted},
            "required": ["items"],
            "additionalProperties": False,
        }
        packed = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
        if len(packed) <= STRICT_SCHEMA_MAX_CHARS:
            adapted = candidate
            name = _WRAPPER_NAME
    compact = json.dumps(adapted, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.md5(compact.encode("utf-8")).hexdigest()
    strict = True
    if adapted.get("type") != "object":
        _warn_once(
            f"root:{digest}",
            "[cerebras] The schema root is not an object, which strict mode demands; "
            "asking without 'strict'",
        )
        strict = False
    if _open_map(adapted):
        _warn_once(
            f"map:{digest}",
            "[cerebras] The schema declares an open-keyed object, which strict mode "
            "refuses; asking without 'strict'",
        )
        strict = False
    if len(compact) > STRICT_SCHEMA_MAX_CHARS:
        _warn_once(
            f"size:{digest}",
            f"[cerebras] The schema measures {len(compact)} characters (strict mode's "
            f"limit: {STRICT_SCHEMA_MAX_CHARS}); asking without 'strict'",
        )
        strict = False
    return {
        "type": "json_schema",
        "json_schema": {"name": name, "strict": strict, "schema": adapted},
    }


def _warn_once(digest: str, message: str) -> None:
    """Log `message` the first time this process sees `digest`."""
    if digest in _WARNED:
        return
    _WARNED.add(digest)
    logger.warning(message)


def _prompt_text(body: dict) -> str:
    """Flatten a request's messages into text, only to size the call before it goes out.

    `record` replaces the estimate with the exact figure the moment the answer lands, so an
    error here never accumulates across calls.
    """
    parts: list[str] = []
    for message in body.get("messages") or []:
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            parts.extend(str(p.get("text", "")) for p in content if isinstance(p, dict))
    return "\n".join(parts)


def _retry_wait(response: httpx.Response, attempt: int) -> float:
    """Seconds to wait before retrying: what `Retry-After` asks for, else a backoff."""
    try:
        wait = float(response.headers.get("retry-after", ""))
    except ValueError:
        wait = float(2**attempt)
    return min(max(wait, 1.0), 60.0)


def _sleep(seconds: float) -> None:
    """Wait in one-second slices, checking for a cancellation between each.

    `Retry-After` reaches 60 s here, and a single `time.sleep` of that is a minute in which
    a stop cannot land — the same defect, on a smaller scale, as an uninterruptible model
    call. Same idiom as the budget ledger's own hold.
    """
    deadline = time.monotonic() + seconds
    while True:
        progress.checkpoint()
        left = deadline - time.monotonic()
        if left <= 0:
            return
        time.sleep(min(left, 1.0))


def _usage(response: httpx.Response) -> tuple[int, int]:
    """What the ledger charges the call, taken from the answer rather than guessed.

    `usage` is exact and arrives with the reply, while the server's own
    `remaining-tokens-*` headers were measured to lag: a 74-token call and a 20-token call
    each moved the daily counter by 6.
    """
    try:
        usage = response.json().get("usage") or {}
    except (ValueError, AttributeError):
        return 0, 0
    return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


_shared: CerebrasEngine | None = None
_shared_base: str | None = None


class HybridEngine:
    """One engine over two backends, routed per model by `CEREBRAS_MODELS`.

    Everything not named there — the guardrail and the embedder included — stays on Ollama,
    and residency, pulls, deletes and the idle release only ever mean that half, remote
    weights having nothing to load or free.
    """

    name = "cerebras+ollama"

    def __init__(self):
        """Build both backends; which one serves a call is decided per model."""
        self._ollama = OllamaEngine()
        self._cerebras = CerebrasEngine()

    def is_available(self) -> bool:
        """Whether the LOCAL half answers, which is what this process cannot do without.

        A Cerebras outage surfaces as a readable error on the first remote call, instead of
        costing every open tab a transatlantic round trip every 15 s.
        """
        return self._ollama.is_available()

    def generate(self, model: str, prompt: str, **kwargs) -> GenerationResponse:
        """Ask the backend that serves `model` for one answer."""
        return self._backend(model).generate(model=model, prompt=prompt, **kwargs)

    def generate_stream(self, model: str, prompt: str, **kwargs) -> GenerationResponse:
        """Stream one answer from the backend that serves `model`."""
        return self._backend(model).generate_stream(model=model, prompt=prompt, **kwargs)

    def embed(self, model: str, text: str) -> list[float]:
        """Embed one text on the backend that serves `model`."""
        return self._backend(model).embed(model, text)

    def embed_batch(self, model: str, texts: list[str]) -> list[list[float]]:
        """Embed several texts on the backend that serves `model`."""
        return self._backend(model).embed_batch(model, texts)

    def capabilities(self, model: str) -> list[str]:
        """What `model` declares it can do, asked of the backend that serves it."""
        return self._backend(model).capabilities(model)

    def supports_thinking(self, model: str) -> bool:
        """Whether `model` has a reasoning mode to ask for."""
        return self._backend(model).supports_thinking(model)

    def supports_vision(self, model: str) -> bool:
        """Whether `model` can read an image."""
        return self._backend(model).supports_vision(model)

    def _backend(self, model: str):
        """The backend that serves `model`."""
        return self._cerebras if self._remote(model) else self._ollama

    def installed_models(self) -> list[str]:
        """The names of every model this engine can serve, local and remote."""
        return [info["model"] for info in self.installed_models_detail()]

    def installed_models_detail(self) -> list[dict]:
        """Every model this engine can serve, marked with which half serves it.

        The remote half is exactly what `remote_models` routes — Cerebras' whole catalogue,
        so the panel can point a phase at any of it, plus the declared list, which is what
        keeps a required remote model from reading as "sin instalar" during a blip.
        """
        local = self._ollama.installed_models_detail()
        remote = sorted(self.remote_models())
        return local + [{"model": model, "size": None, "remote": True} for model in remote]

    def remote_models(self) -> frozenset[str]:
        """Which models this engine serves remotely: the catalogue plus the declared list."""
        return frozenset(config.CEREBRAS_MODELS) | self._cerebras.known_models()

    def running_models(self) -> list[dict]:
        """What is resident on the GPU; a remote model occupies nothing."""
        return self._ollama.running_models()

    def unload(self, model: str, is_embedding: bool = False) -> bool:
        """Free `model` from the GPU; a remote one has nothing to free."""
        if self._remote(model):
            return True
        return self._ollama.unload(model, is_embedding=is_embedding)

    def unload_all(self) -> list[str]:
        """Free every resident model, which can only ever mean the local half."""
        return self._ollama.unload_all()

    def ensure_model(self, model: str) -> bool:
        """Check `model` is available: installed locally, or in Cerebras' catalogue."""
        if not self._remote(model):
            return self._ollama.ensure_model(model)
        try:
            catalog = self._cerebras.catalog()
        except InferenceError as e:
            logger.warning(f"[cerebras] Could not check '{model}': {e}")
            return False
        if model not in catalog:
            logger.warning(f"[cerebras] '{model}' is not in Cerebras' catalogue")
            return False
        return True

    def pull(self, model: str, on_progress=None) -> None:
        """Download `model`; a remote one has nothing to download."""
        if self._remote(model):
            raise InferenceError(f"'{model}' se sirve en Cerebras; no hay nada que descargar")
        self._ollama.pull(model, on_progress)

    def delete(self, model: str) -> None:
        """Remove `model` from disk; a remote one is not on ours."""
        if self._remote(model):
            raise InferenceError(f"'{model}' se sirve en Cerebras; no hay nada que borrar")
        self._ollama.delete(model)

    def _remote(self, model: str) -> bool:
        """Whether `model` is routed to Cerebras: in its catalogue, or declared as such.

        The catalogue is what makes every model Cerebras serves usable without editing
        anything; `CEREBRAS_MODELS` is what stands when the catalogue cannot be read, and
        it also names a model the catalogue does not list.
        """
        return model in config.CEREBRAS_MODELS or model in self._cerebras.known_models()


def catalog() -> list[str]:
    """Cerebras' catalogue, readable without activating the engine.

    Shared so the TTL survives between requests, and rebuilt when the base URL changes.
    """
    global _shared, _shared_base
    base = str(config.CEREBRAS_BASE_URL)
    if _shared is None or _shared_base != base:
        _shared = CerebrasEngine()
        _shared_base = base
    return _shared.catalog()
