"""The remote half: Cerebras' OpenAI-compatible API, gated by the spending ledger."""

import json
import time

import httpx
from loguru import logger

from ...utils import progress, repetition
from .. import usage
from ..thinking import split_thinking
from ..types import GenerationResponse, InferenceError, Sampling, TokenSink
from . import budget as cerebras_budget
from .budget import Budget
from .schema import (
    _WRAPPER_NAME,
    _unwrap,
    _warn_once,
    reasoning_effort,
    response_format,
)

# Cerebras' catalogue lists image input for both families, ten per request; gpt-oss does
# not take images.
_VISION_PREFIXES = ("gemma-4", "qwen-3.8")
_RETRY_STATUSES = (429, 503)
_MAX_ATTEMPTS = 5
_CATALOG_TTL_SECONDS = 300.0
# How long a failed catalogue read stands before the next attempt: routing asks for the
# catalogue on every call, and a dead API must not cost every one of them a round trip.
_CATALOG_RETRY_SECONDS = 60.0



class CerebrasEngine:
    """The remote half: Cerebras' OpenAI-compatible API, gated by the spending ledger."""

    name = "cerebras"

    def __init__(self, base_url: str, api_key: str, budget: Budget):
        """Open the client on `base_url` with `api_key`, charging every call to `budget`."""
        self._base_url = base_url
        self._budget = budget
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(600.0, connect=10.0),
        )
        self._warned: set[str] = set()
        self._catalog: tuple[float, list[str]] | None = None
        self._catalog_failed_at: float | None = None

    def close(self) -> None:
        """Close the HTTP connection pool."""
        self._client.close()

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
                f"({_endpoint_label(self._base_url, '/models')}); el detalle está en el registro"
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
        sampling: Sampling | None = None,
    ) -> GenerationResponse:
        """Stream one answer, feeding each token to `on_token` as it arrives.

        The claim IS the room: it is booked at the estimate before the call goes out, so a
        second job on the remote lane sees a smaller window rather than the same one.
        Releasing it at the end is a no-op once the call has been recorded — the room only
        comes back when the call never happened.
        """
        if on_token is None:
            return self.generate(model=model, prompt=prompt, think=think, sampling=sampling)

        body = self._body(model, prompt, think, None, None, sampling, None)
        body["stream"] = True
        # A streamed answer carries no `usage` unless it is asked for, and without it the
        # ledger would charge a whole generation zero tokens.
        body["stream_options"] = {"include_usage": True}

        ledger = self._budget
        phase = progress.current_activity()
        claim = ledger.wait(model, cerebras_budget.estimate_tokens(prompt), phase)

        try:
            with self._client.stream("POST", "/chat/completions", json=body) as response:
                if response.status_code != 200:
                    response.read()
                    ledger.record(model, phase, 0, 0, response.headers, claim=claim)
                    raise InferenceError(
                        _remote_error(self._base_url, response.status_code, model, response.text)
                    )
                answer, thinking, prompt_tokens, completion_tokens = _consume_stream(
                    response, on_token
                )
                ledger.record(
                    model, phase, prompt_tokens, completion_tokens, response.headers, claim=claim
                )
                usage.record(self.name, model, prompt_tokens, completion_tokens)
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
        sampling: Sampling | None = None,
        format: dict | str | None = None,
        max_output_tokens: int | None = None,
        stop_on_loop: bool = False,
    ) -> GenerationResponse:
        """Ask `model` for one answer, unwrapping it when the schema had to be wrapped.

        `finish_reason == "length"` is the API saying the answer hit `max_completion_tokens`;
        it travels as `truncated` so the caller can refuse a cut answer instead of keeping
        it as a short one. `stop_on_loop` is answered AFTER the call here, on the whole
        text and anywhere in it (`repetition.detect`): this endpoint answers 4 096 tokens
        in about two seconds, and a stream cut short would arrive without the `usage` the
        ledger charges the call by — so what the flag buys on this route is the verdict,
        not the tokens. Anywhere and not only the tail, because a model that stops
        repeating on its own then closes the fence and finishes the page.
        """
        body = self._body(
            model, prompt, think, system, images, sampling, format,
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
        found = repetition.detect(content) if stop_on_loop else None
        return split_thinking(
            content,
            reasoning,
            choice.get("finish_reason") == "length",
            found.unit if found is not None else None,
        )

    def _body(
        self,
        model: str,
        prompt: str,
        think: bool | str | None,
        system: str | None,
        images: list[str] | None,
        sampling: Sampling | None,
        format: dict | str | None,
        max_output_tokens: int | None = None,
    ) -> dict:
        """Assemble the chat-completions request for one call.

        Images travel as base64 data URLs typed by their own first bytes — a scanned page is
        sent as JPEG — and a model that cannot read one is refused up front rather than
        answering emptily. A top-k is not sent: the API documents temperature and top-p
        and nothing else of the sampler, so a set one is dropped with a warning once per
        model and the rest of the sampling travels as asked.
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
        if sampling is not None:
            body["temperature"] = sampling.temperature
            if sampling.top_p is not None:
                body["top_p"] = sampling.top_p
            if sampling.top_k is not None:
                _warn_once(
                    self._warned,
                    f"top_k:{model}",
                    f"[cerebras] '{model}' is sent no top_k (the API does not document it); "
                    f"the {sampling.top_k} asked for is dropped",
                )
        if max_output_tokens is not None:
            body["max_completion_tokens"] = max_output_tokens
        effort = reasoning_effort(think)
        if effort is not None:
            body["reasoning_effort"] = effort
        shaped = response_format(format, self._warned)
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
        ledger = self._budget
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
                raise InferenceError(_remote_error(self._base_url, response.status_code, model, response.text))
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
        usage.record(self.name, model, prompt_tokens, completion_tokens)
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


def _remote_error(base_url: str, status: int, model: str, body: str) -> str:
    """Phrase a remote failure for the panel: the status and the endpoint, not the body.

    Same rule as `ollama._upstream_error` — what a remote API answers is its text, not
    ours, and these messages travel to the panel as the job's failure.
    """
    logger.debug(f"[cerebras] Body of error {status} for '{model}': {body[:300]}")
    return (
        f"Cerebras respondió {status} para '{model}' "
        f"({_endpoint_label(base_url, '/chat/completions')}); el detalle está en el registro"
    )


def _endpoint_label(base_url: str, path: str) -> str:
    """The full URL of `path`, for an error an operator has to act on."""
    return f"{str(base_url).rstrip('/')}{path}"


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
