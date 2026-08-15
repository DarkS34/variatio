from fastapi import APIRouter

from variant_generator import config, inference

from .. import deps, runtime, settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict:
    ws = settings.workspace()
    available = inference.is_available()
    required = inference.required_models()

    installed: list[str] = []
    if available:
        try:
            installed = inference.installed_models()
        except Exception:  # noqa: BLE001 - a listing failure is not a fatal condition
            installed = []

    # Ollama reports "name:tag"; config asks for the same form, but be lenient about
    # a missing tag so a manually pulled model is not reported as absent.
    installed_names = {m.split(":")[0] for m in installed}
    missing = sorted(
        {
            model
            for model in required.values()
            if installed and model not in installed and model.split(":")[0] not in installed_names
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
        },
        "context_ready": deps.is_ready(),
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
