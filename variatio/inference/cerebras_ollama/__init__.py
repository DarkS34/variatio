"""The `cerebras+ollama` engine: Cerebras' API for the models it serves, Ollama for the rest."""

from .hybrid import HybridEngine

__all__ = ["HybridEngine"]
