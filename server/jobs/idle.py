"""Release the GPU when nobody has asked for it in a long while.

`OLLAMA_KEEP_ALIVE=24h` is deliberate: it keeps the three models resident through a
working session, which is exactly what is wanted while someone is working. Its flaw is
that it cannot tell a pause from an abandonment, and an installation nobody has touched
since yesterday keeps ~29 GiB of a card that is shared.

This thread is that distinction and nothing more: it reads the queue's clock — the queue
is where ALL of this process's model traffic goes through — and once it has gone
`IDLE_UNLOAD_SECONDS` without a job, it unloads whatever is resident. It is not a
replacement for the keep-alive nor a shorter timer: the models stay warm for the whole
session, and are released once, when the session is actually over.

It reads the WHOLE queue's clock and not the local lane's, which looks like the obvious
refinement now that a job can be purely remote and is not one: the embedder and the
guardrail are excluded from the lane calculation on purpose, and both are local, so a job
holding only the remote lane is still calling Ollama every few seconds. Releasing under it
would unload the very models it is using.

Unloading is free to undo: the next call loads them again by itself.
"""

import threading

from loguru import logger

from variatio import config
from variatio.core import inference

from .runner import JobRunner


class IdleUnloader:
    def __init__(self, runner: JobRunner):
        self.runner = runner
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        # One unload per idle period: without this, every turn of the loop would ask `/api/ps`
        # again and send an unload with nothing left to unload, and an idle server would write one
        # log line per minute.
        self._released = False

    def start(self) -> None:
        if self._thread is not None or config.IDLE_UNLOAD_SECONDS <= 0:
            return
        self._thread = threading.Thread(target=self._run, name="idle-unloader", daemon=True)
        self._thread.start()
        logger.info(
            f"Vigilando la inactividad: la GPU se libera tras "
            f"{config.IDLE_UNLOAD_SECONDS // 60} minuto(s) sin trabajos"
        )

    def stop(self, timeout: float = 2.0) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stopping.wait(config.IDLE_UNLOAD_POLL_SECONDS):
            try:
                self._tick()
            except Exception as e:  # noqa: BLE001 - a watchdog must not take the process down
                logger.warning(f"El vigilante de inactividad falló esta vuelta: {e}")

    def _tick(self) -> None:
        idle = self.runner.idle_seconds()
        if idle < config.IDLE_UNLOAD_SECONDS:
            self._released = False
            return
        if self._released:
            return

        self._released = True
        release_gpu(f"tras {int(idle // 60)} minuto(s) de inactividad")


def release_gpu(reason: str) -> list[str]:
    if not inference.is_available():
        return []
    released = inference.unload_all()
    if released:
        logger.info(
            f"{len(released)} modelo(s) descargados de la GPU {reason}: {', '.join(released)}"
        )
    return released
