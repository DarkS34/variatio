"""Release the GPU when nobody has asked for it in a long while.

`OLLAMA_KEEP_ALIVE=24h` keeps the models resident through a working session, which is what
is wanted while somebody is working; what it cannot do is tell a pause from an abandonment,
and an installation untouched since yesterday holds ~29 GiB of a shared card.

This thread is that distinction and nothing more. It reads the queue's clock — every model
call of this process goes through the queue — and after `IDLE_UNLOAD_SECONDS` without a job
it unloads whatever is resident. Not a shorter keep-alive: the models stay warm for the
whole session and are released once, when the session is over.

The clock counts EVERY lane, never only the local one. The embedder and the guardrail are
excluded from the lane calculation and both are local, so a job holding only the remote lane
is still calling Ollama every few seconds and releasing under it would unload what it uses.

Unloading is free to undo: the next call loads the models again by itself.
"""

import threading

from loguru import logger

from variatio import config
from variatio.core import inference

from .runner import JobRunner


class IdleUnloader:
    """A watchdog thread that unloads the models once the queue has been quiet long enough."""

    def __init__(self, runner: JobRunner):
        """Watch this runner's clock. Nothing runs until `start()`."""
        self.runner = runner
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        # One unload per idle period. Without it every turn would re-read `/api/ps` and
        # unload nothing, and an idle server would log a line a minute.
        self._released = False

    def start(self) -> None:
        """Start watching, unless already started or the unload is switched off."""
        if self._thread is not None or config.IDLE_UNLOAD_SECONDS <= 0:
            return
        self._thread = threading.Thread(target=self._run, name="idle-unloader", daemon=True)
        self._thread.start()
        logger.info(
            f"Vigilando la inactividad: la GPU se libera tras "
            f"{config.IDLE_UNLOAD_SECONDS // 60} minuto(s) sin trabajos"
        )

    def stop(self, timeout: float = 2.0) -> None:
        """Ask the thread to leave and wait briefly for it."""
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        """Poll until told to stop, surviving any failure of one turn."""
        while not self._stopping.wait(config.IDLE_UNLOAD_POLL_SECONDS):
            try:
                self._tick()
            except Exception as e:  # noqa: BLE001 - a watchdog must not take the process down
                logger.warning(f"El vigilante de inactividad falló esta vuelta: {e}")

    def _tick(self) -> None:
        """Release the GPU once if the queue has been idle long enough; rearm when it moves."""
        idle = self.runner.idle_seconds()
        if idle < config.IDLE_UNLOAD_SECONDS:
            self._released = False
            return
        if self._released:
            return

        self._released = True
        release_gpu(f"tras {int(idle // 60)} minuto(s) de inactividad")


def release_gpu(reason: str) -> list[str]:
    """Unload every resident model and return their names; empty when the engine is away."""
    if not inference.is_available():
        return []
    released = inference.unload_all()
    if released:
        logger.info(
            f"{len(released)} modelo(s) descargados de la GPU {reason}: {', '.join(released)}"
        )
    return released
