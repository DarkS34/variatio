from fastapi import APIRouter

from variatio import config
from variatio.core import inference

from .. import auth, deps, runtime

router = APIRouter(prefix="/api", tags=["health"], dependencies=[auth.VIEW])


@router.get("/health")
def health(access: auth.Access = auth.VIEW) -> dict:
    ws = access.ws
    available = inference.is_available()
    required = inference.required_models()

    installed: list[str] = []
    running: list[dict] = []
    if available:
        try:
            installed = inference.installed_models()
        except Exception:  # noqa: BLE001 - a listing failure is not a fatal condition
            installed = []
        try:
            running = inference.running_models()
        except Exception:  # noqa: BLE001 - idem: no residency reading, not a broken engine
            running = []

    # Ollama reports "name:tag"; config asks for the same form, but be lenient about
    # a missing tag so a manually pulled model is not reported as absent. A remotely
    # served model is never "missing": there is no disk for it to be missing from.
    remote = inference.remote_models()
    installed_names = {m.split(":")[0] for m in installed}
    missing = sorted(
        {
            model
            for model in required.values()
            if installed
            and model not in remote
            and model not in installed
            and model.split(":")[0] not in installed_names
        }
    )

    return {
        "engine": inference.engine_name(),
        "host": config.OLLAMA_HOST,
        "available": available,
        "models": {
            "required": required,
            "installed": installed,
            "missing": missing,
            "remote": sorted(remote & set(required.values())),
            # What the engine has resident right now, with its VRAM and until when. It is the only
            # real measure of what the machine is using: `required` only says what `config.py` names,
            # and a named constant is not a loaded model.
            "running": running,
        },
        # Whether *this* workspace's indices are warm, not whether any are: with a registry
        # of contexts the old process-wide answer would have been true for somebody else.
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
