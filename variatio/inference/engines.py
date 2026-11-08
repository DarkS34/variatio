"""The engines one process holds: built when first asked for, shared by name, closed on demand.

This is what replaces a module-level engine. The OWNER of a process builds one `EngineSet` —
the CLI's `main`, the build worker's `main`, the server in `core/process.py` — and the
library never builds an engine of its own: it reads the one the caller fixed for the
current context (`inference.using`).

Two engines over the same Ollama server share ONE `OllamaEngine`: the `ollama` engine is that
instance, and the hybrid's local half is the same object. They share its client and its
capability and listing caches; the models resident on the GPU are the server's and were
shared already. The local instance is closed when the last engine that uses its host goes.

An engine nobody uses has no instance. The owner says which engines are wanted (`keep`, the
server's: the engines its accounts run on) and a job holds the one it runs on while it runs
(`hold`/`release`); an engine neither wanted nor held is closed. A process that never calls
`keep` (the CLI, a build) keeps whatever it built.
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
        self._lock = threading.RLock()
        self._engines: dict[str, Engine] = {}
        self._hosts: dict[str, str] = {}
        self._locals: dict[str, Engine] = {}
        self._wanted: set[str] | None = None
        self._held: dict[str, int] = {}

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

    def keep(self, names: set[str]) -> None:
        """Make `names` the wanted engines: build each one, close every other nobody holds.

        An engine that cannot be built (a name no longer known) is logged and skipped.
        """
        with self._lock:
            self._wanted = set(names)
            for name in sorted(names):
                try:
                    self.get(name)
                except InferenceError as e:
                    logger.warning(f"[inference] Not building the engine '{name}': {e}")
            for name in self.names():
                if name not in self._wanted and not self._held.get(name):
                    self.close(name)

    def hold(self, name: str) -> Engine:
        """The engine called `name`, held open until `release`: what a running job does."""
        with self._lock:
            engine = self.get(name)
            self._held[name] = self._held.get(name, 0) + 1
            return engine

    def release(self, name: str) -> None:
        """Let go of one `hold`; the last one closes an engine that is no longer wanted."""
        with self._lock:
            left = self._held.get(name, 0) - 1
            if left > 0:
                self._held[name] = left
                return
            self._held.pop(name, None)
            if self._wanted is not None and name not in self._wanted:
                self.close(name)

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
