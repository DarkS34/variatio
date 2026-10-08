"""What the engine and this workspace's indices are doing right now.

Declares `auth.VIEW`: it reports on the machine, but it also reports this instance's
paths and whether its context is warm, so it is not public.

The engine is read once every `READ_EVERY` seconds for the whole process, by one thread at
a time, and every request in between takes that reading: a class has a hundred tabs open, each
polling this route every 15 s, and each poll crossed the SSH tunnel three times. While one
thread reads, the others answer with the reading before it, and only the very first waits.
The installed listing is also cached for 30 s inside `core.inference`. The panel's «Motor»
tab reads the engine live from `/api/admin/engine`, so what it shows of the GPU is never
five seconds old.
"""

import threading
import time
from dataclasses import dataclass

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from variatio import config, entrypoints
from variatio.core import inference

from .. import auth, deps, features, singletons

router = APIRouter(prefix="/api", tags=["health"], dependencies=[auth.VIEW])

# How old the shared reading of the engine may be, in seconds.
READ_EVERY = 5.0


@dataclass(frozen=True)
class EngineReading:
    """What the engine said at one moment: whether it answers, and its models."""

    at: float
    available: bool
    installed: list[str]
    running: list[dict]


_reading: EngineReading | None = None
_reading_lock = threading.Lock()
_clock = time.monotonic


def engine_reading() -> EngineReading:
    """Return the shared reading of the engine, reading it again when it is too old.

    One thread reads at a time; the others take the reading before it rather than queue
    behind the tunnel. Only when there is no reading at all does a request wait for one.
    """
    global _reading
    current = _reading
    if current is not None and _clock() - current.at < READ_EVERY:
        return current
    if not _reading_lock.acquire(blocking=current is None):
        return current
    try:
        current = _reading
        if current is not None and _clock() - current.at < READ_EVERY:
            return current
        available = inference.is_available()
        installed, running = _listings() if available else ([], [])
        _reading = EngineReading(_clock(), available, installed, running)
        return _reading
    finally:
        _reading_lock.release()


def forget_reading() -> None:
    """Drop the shared reading, so the next request reads the engine again."""
    global _reading
    _reading = None


def _listings() -> tuple[list[str], list[dict]]:
    """Read what is installed and what is resident, each degrading to an empty list."""
    installed: list[str] = []
    running: list[dict] = []
    try:
        installed = inference.installed_models()
    except Exception:  # noqa: BLE001 - a listing failure is not a fatal condition
        installed = []
    try:
        running = inference.running_models()
    except Exception:  # noqa: BLE001 - idem: no residency reading, not a broken engine
        running = []
    return installed, running


def _missing_models(required: dict, installed: list[str], remote: set[str]) -> list[str]:
    """Name the models the configuration asks for that are not on the engine's disk.

    Ollama reports `name:tag` and the configuration asks for the same form, but a missing
    tag is tolerated so a manually pulled model is not reported as absent. A remotely
    served model is never missing: there is no disk for it to be missing from. An empty
    `installed` means the listing failed, and nothing is reported missing on that.
    """
    installed_names = {m.split(":")[0] for m in installed}
    return sorted(
        {
            model
            for model in required.values()
            if installed
            and model not in remote
            and model not in installed
            and model.split(":")[0] not in installed_names
        }
    )


@router.get("/health")
def health(access: auth.Access = auth.VIEW, db: DbSession = Depends(auth.db)) -> dict:
    """Answer the engine's reachability, its models, and this workspace's own paths."""
    ws = access.ws
    reading = engine_reading()
    available, installed, running = reading.available, reading.installed, reading.running
    required = _required(db)

    remote = inference.remote_models()

    return {
        "engine": inference.engine_name(),
        "host": config.OLLAMA_HOST,
        "available": available,
        "models": {
            "required": required,
            # What a commission may choose between, the default first. It is read by the
            # generate screen, so it travels here rather than on a route of its own: the
            # form already polls this one to know whether the engine answers at all.
            "offered": entrypoints.generation_models(),
            # Which of those may not have their effort adjusted per commission. It rides
            # here for the same reason `offered` does: the form already polls this route.
            "fixed_effort": entrypoints.fixed_effort_models(),
            # And with which level each of those is called, so the form shows the one the
            # installation declared instead of the last one its own slider held.
            "fixed_effort_levels": entrypoints.fixed_effort_levels(),
            "installed": installed,
            "missing": _missing_models(required, installed, remote),
            "remote": sorted(remote & set(required.values())),
            # Resident right now, with its VRAM and until when. `required` only says what
            # the configuration names, and a named constant is not a loaded model.
            "running": running,
        },
        # Whether THIS workspace's indices are warm: with a registry of contexts a
        # process-wide answer would report somebody else's instance.
        "context_ready": deps.is_ready(ws.slug),
        "workspace": ws.slug,
        "paths": {
            "artifacts": str(ws.artifacts_dir),
            "raw_exemplars": str(ws.raw_exemplars_dir),
            "raw_corpus": str(ws.raw_corpus_dir),
            "raw_exemplars_exists": ws.raw_exemplars_dir.is_dir(),
            "raw_corpus_exists": ws.raw_corpus_dir.is_dir(),
        },
        "busy": singletons.runner.is_busy(),
    }


def _required(db: DbSession) -> dict[str, str]:
    """Return the models the registry asks for, without those only a switched-off function calls.

    A setting of an optional function is keyed under the function's name (`tutor.models.reply`),
    so a function that is off for everybody does not report its own model as missing.
    """
    off = tuple(
        f"{feature}." for feature in features.FEATURES if features.mode(db, feature) == features.OFF
    )
    return {
        key: model for key, model in inference.required_models().items() if not key.startswith(off)
    }
