"""The contract every inference engine fulfils, so the boundary never asks which one it holds.

An engine is one way of serving models: `ollama` (a local server) or `cerebras+ollama`
(Cerebras' API for what it serves, Ollama for the rest), and later `vllm` and `sglang`. Each
lives in its own package under `inference/` and subclasses `Engine`; nothing outside
`inference/` names a concrete engine class.
"""

from abc import ABC, abstractmethod

from .types import GenerationResponse, ProgressSink, Sampling, TokenSink


class Engine(ABC):
    """One way of serving models: generation, embeddings, and what is installed and resident.

    `name` is the value of the `engine.name` setting that selects it and never follows a
    module rename (D-009). `manages_models` says whether `pull` and `delete` mean anything:
    a server that loads a fixed set of models at start has nothing to download, and refuses
    both with an `InferenceError`.
    """

    name: str
    manages_models: bool = True

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the engine answers at all; never raises."""

    @abstractmethod
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
        """Ask `model` for one answer, with the reasoning split out of it."""

    @abstractmethod
    def generate_stream(
        self,
        model: str,
        prompt: str,
        think: bool | str | None = None,
        on_token: TokenSink | None = None,
        sampling: Sampling | None = None,
    ) -> GenerationResponse:
        """Ask `model` for one answer, feeding each token to `on_token` as it arrives."""

    @abstractmethod
    def embed(self, model: str, text: str) -> list[float]:
        """Embed one text."""

    @abstractmethod
    def embed_batch(self, model: str, texts: list[str]) -> list[list[float]]:
        """Embed several texts in one call, in the order they were given."""

    @abstractmethod
    def capabilities(self, model: str) -> list[str]:
        """What `model` declares it can do, in Ollama's vocabulary (`thinking`, `vision`, …)."""

    @abstractmethod
    def supports_thinking(self, model: str) -> bool:
        """Whether `model` has a reasoning mode to ask for."""

    @abstractmethod
    def supports_vision(self, model: str) -> bool:
        """Whether `model` can read an image."""

    @abstractmethod
    def installed_models(self) -> list[str]:
        """The names of the models this engine can serve."""

    @abstractmethod
    def installed_models_detail(self) -> list[dict]:
        """The models this engine can serve, with their sizes and where they are served."""

    @abstractmethod
    def remote_models(self) -> frozenset[str]:
        """Which of the engine's models are served remotely; empty on a purely local one."""

    @abstractmethod
    def running_models(self) -> list[dict]:
        """What is resident on the GPU right now."""

    @abstractmethod
    def unload(self, model: str, is_embedding: bool = False) -> bool:
        """Free `model` from the GPU; returns whether it went."""

    @abstractmethod
    def unload_all(self) -> list[str]:
        """Free every resident model, returning the ones that went."""

    @abstractmethod
    def ensure_model(self, model: str) -> bool:
        """Make sure `model` can be served, downloading it if the engine manages models."""

    @abstractmethod
    def pull(self, model: str, on_progress: ProgressSink | None = None) -> None:
        """Download `model` to the engine's disk."""

    @abstractmethod
    def delete(self, model: str) -> None:
        """Remove `model` from the engine's disk."""

    @abstractmethod
    def close(self) -> None:
        """Release the engine's connections; the engine is not used after this."""
