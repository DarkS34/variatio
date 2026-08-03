from fastapi import APIRouter

from variant_generator import config, inference

from .. import deps, runtime

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict:
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
        "paths": {
            "instance": str(config.INSTANCE_DIR),
            "raw_exemplars": str(config.RAW_EXEMPLARS_BANK_DIR),
            "raw_corpus": str(config.RAW_CORPUS_DIR),
            "raw_exemplars_exists": config.RAW_EXEMPLARS_BANK_DIR.is_dir(),
            "raw_corpus_exists": config.RAW_CORPUS_DIR.is_dir(),
        },
        "busy": runtime.runner.is_busy(),
    }
