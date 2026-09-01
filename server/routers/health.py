"""What the engine and this workspace's indices are doing right now.

Declares `auth.VIEW`: it reports on the machine, but it also reports this instance's
paths and whether its context is warm, so it is not public.

The *installed* listing is cached for 30 s inside `core.inference` — what is on disk only
changes on a pull or a delete, and every open tab polls this route across the SSH tunnel.
Residency is NEVER cached: `running_models()` is the live measurement the panel's card
exists to show, and caching it would make the panel lie about the GPU.
"""

from fastapi import APIRouter

from variatio import config, stages
from variatio.core import inference

from .. import auth, deps, runtime

router = APIRouter(prefix="/api", tags=["health"], dependencies=[auth.VIEW])


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
def health(access: auth.Access = auth.VIEW) -> dict:
    """Answer the engine's reachability, its models, and this workspace's own paths."""
    ws = access.ws
    available = inference.is_available()
    required = inference.required_models()

    installed: list[str] = []
    running: list[dict] = []
    if available:
        installed, running = _listings()

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
            "offered": stages.generation_models(),
            # Which of those may not have their effort adjusted per commission. It rides
            # here for the same reason `offered` does: the form already polls this route.
            "fixed_effort": stages.fixed_effort_models(),
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
            "instance": str(ws.instance_dir),
            "raw_exemplars": str(ws.raw_exemplars_dir),
            "raw_corpus": str(ws.raw_corpus_dir),
            "raw_exemplars_exists": ws.raw_exemplars_dir.is_dir(),
            "raw_corpus_exists": ws.raw_corpus_dir.is_dir(),
        },
        "busy": runtime.runner.is_busy(),
    }
