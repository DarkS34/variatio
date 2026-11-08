"""One engine over two backends: Cerebras for the models it serves, Ollama for the rest.

Everything not named in `CEREBRAS_MODELS` or in Cerebras' catalogue — the guardrail and the
embedder always included — stays on Ollama, so residency, pulls, deletes and the idle release
only ever mean the local half.
"""

from loguru import logger

from ... import config
from ..interface import Engine
from ..ollama import OllamaEngine
from ..types import GenerationResponse, InferenceError
from .remote import CerebrasEngine


class HybridEngine(Engine):
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

    def close(self) -> None:
        """Close both backends."""
        self._cerebras.close()
        self._ollama.close()

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
