"""Model downloads, tracked while they run beside the job queue.

A pull is network and disk and never the GPU, so it must not wait behind a two-hour build:
each one gets a thread of its own and the queue never sees it.
"""

import threading
import time

from loguru import logger

from variatio.core import inference

KEEP_FINISHED = 10


class PullTracker:
    """The downloads this process has started, running and recently finished."""

    def __init__(self) -> None:
        """Start with no pulls on record."""
        self._lock = threading.Lock()
        self._pulls: dict[str, dict] = {}

    def start(self, model: str, user: str | None = None) -> dict:
        """Begin downloading a model in its own thread, or return the pull already running."""
        model = model.strip()
        if not model:
            raise ValueError("Di qué modelo descargar, con su etiqueta: nombre:etiqueta")
        with self._lock:
            current = self._pulls.get(model)
            if current is not None and current["status"] == "running":
                return dict(current)
            entry = {
                "model": model,
                "status": "running",
                "completed": 0,
                "total": 0,
                "started_at": time.time(),
                "finished_at": None,
                "error": None,
                "user": user,
            }
            self._pulls[model] = entry
            self._prune()
        threading.Thread(
            target=self._run, args=(model,), name=f"pull-{model}", daemon=True
        ).start()
        return dict(entry)

    def active(self) -> list[dict]:
        """List the pulls currently downloading."""
        with self._lock:
            return [dict(entry) for entry in self._pulls.values() if entry["status"] == "running"]

    def all(self) -> list[dict]:
        """List every pull on record, most recently started first."""
        with self._lock:
            return sorted(
                (dict(entry) for entry in self._pulls.values()),
                key=lambda entry: entry["started_at"],
                reverse=True,
            )

    def is_pulling(self, model: str) -> bool:
        """Report whether one model is downloading right now."""
        with self._lock:
            entry = self._pulls.get(model)
            return entry is not None and entry["status"] == "running"

    def _run(self, model: str) -> None:
        """Download one model, recording a failure as the pull's outcome rather than raising."""

        def on_progress(completed: int, total: int) -> None:
            """Record how far the download has got."""
            with self._lock:
                entry = self._pulls[model]
                entry["completed"] = completed
                entry["total"] = total

        try:
            inference.pull_model(model, on_progress)
            status, error = "succeeded", None
        except Exception as exc:  # noqa: BLE001 - the failure is the record, not a crash
            status, error = "failed", str(exc)
            logger.warning(f"La descarga de '{model}' falló: {exc}")
        with self._lock:
            entry = self._pulls[model]
            entry["status"] = status
            entry["error"] = error
            entry["finished_at"] = time.time()

    def _prune(self) -> None:
        """Forget all but the `KEEP_FINISHED` most recently finished pulls."""
        finished = [
            model for model, entry in self._pulls.items() if entry["status"] != "running"
        ]
        finished.sort(key=lambda model: self._pulls[model]["finished_at"] or 0)
        for model in finished[: max(0, len(finished) - KEEP_FINISHED)]:
            self._pulls.pop(model, None)
