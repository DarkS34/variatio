"""The engines one process holds: built when first asked for, shared by name, closed on demand.

This is what replaces a module-level engine. The OWNER of a process builds one `EngineSet` —
the CLI's `main`, the build worker's `main`, the server in `core/process.py` — and the
library never builds an engine of its own: it reads the one the caller fixed for the
current context (`inference.using`).

Two engines over the same Ollama server share ONE `OllamaEngine`: the `ollama` engine is that
instance, and the hybrid's local half is the same object. They share its client and its
capability and listing caches; the models resident on the GPU are the server's and were
shared already. The local instance is closed when the last engine that uses its host goes.
"""

import threading

from loguru import logger

from .. import config
from .interface import Engine
from .types import InferenceError

ENGINE_NAMES = ("ollama", "cerebras+ollama")


class EngineSet:
    """The engines of one process, keyed by their `engine.name` value."""

    def __init__(self) -> None:
        """Start empty: no engine exists until somebody asks for it."""
        self._lock = threading.Lock()
        self._engines: dict[str, Engine] = {}
        self._hosts: dict[str, str] = {}
        self._locals: dict[str, Engine] = {}

    def default(self) -> Engine:
        """The installation's default engine, `engine.name`, built if it does not exist yet."""
        return self.get(config.INFERENCE_ENGINE)

    def get(self, name: str) -> Engine:
        """The engine called `name`, built on first request and kept until it is closed."""
        with self._lock:
            engine = self._engines.get(name)
            if engine is None:
                engine = self._build(name)
                self._engines[name] = engine
            return engine

    def existing(self, name: str) -> Engine | None:
        """The engine called `name` if it exists; never builds one."""
        with self._lock:
            return self._engines.get(name)

    def names(self) -> list[str]:
        """The engines that exist right now."""
        with self._lock:
            return sorted(self._engines)

    def local_engines(self) -> list[Engine]:
        """One `OllamaEngine` per Ollama host in use: what residency and the GPU mean."""
        with self._lock:
            return list(self._locals.values())

    def close(self, name: str) -> None:
        """Close the engine called `name`, and its local half if no other engine uses it."""
        with self._lock:
            engine = self._engines.pop(name, None)
            host = self._hosts.pop(name, None)
            if engine is None:
                return
            if engine not in self._locals.values():
                _close(engine)
            if host is not None and host not in self._hosts.values():
                _close(self._locals.pop(host))

    def close_all(self) -> None:
        """Close every engine: a change of host, key or engine is only real after this."""
        for name in self.names():
            self.close(name)

    def _build(self, name: str) -> Engine:
        """Build the engine called `name` from its settings; the caller holds the lock.

        The engine packages import the SDKs, so they are reached here rather than at import
        time: importing the boundary stays cheap.
        """
        if name not in ENGINE_NAMES:
            raise InferenceError(
                f"Unknown inference engine '{name}'. Available: {', '.join(ENGINE_NAMES)}"
            )
        host = str(config.OLLAMA_HOST)
        local = self._local(host)
        self._hosts[name] = host
        if name == "ollama":
            return local

        from .cerebras_ollama import HybridEngine
        from .cerebras_ollama.budget import account_ledger
        from .cerebras_ollama.remote import CerebrasEngine

        remote = CerebrasEngine(config.CEREBRAS_BASE_URL, config.CEREBRAS_API_KEY, account_ledger())
        return HybridEngine(local, remote)

    def _local(self, host: str) -> Engine:
        """The `OllamaEngine` on `host`, shared by every engine that uses it."""
        local = self._locals.get(host)
        if local is None:
            from .ollama import OllamaEngine

            local = OllamaEngine(host)
            self._locals[host] = local
        return local


def _close(engine: Engine) -> None:
    """Close `engine`, logging rather than raising: a failed close must not stop the others."""
    try:
        engine.close()
    except Exception as e:  # noqa: BLE001 - closing is best-effort by nature
        logger.warning(f"[inference] Could not close the engine '{engine.name}': {e}")
