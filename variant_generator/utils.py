from collections.abc import Callable

from loguru import logger

from . import config, inference, progress
from .prompts import json_repair_prompt


def prepare_models() -> None:
    all_models = sorted(
        {value for name, value in vars(config).items() if name.endswith("_LLM")}
    )

    logger.info(f"Initializing models on '{inference.engine_name()}' engine")
    ensure_models(all_models, "runtime")


def ensure_models(models: list[str], label: str) -> None:
    unique = list(dict.fromkeys(models))
    logger.info(f"Preparing {label} model(s): {', '.join(unique)}")

    failed = [m for m in unique if not inference.ensure_model(m)]
    if failed:
        raise RuntimeError(f"Failed to install model(s): {', '.join(failed)}")

    for m in unique:
        progress.checkpoint()
        inference.warmup(m, is_embedding=(m in config.EMBEDDING_MODELS))

    logger.success(f"{label} models ready")


def parse_with_repair(
    response: str,
    parse: Callable[[str], tuple[object | None, str | None]],
    repair_model: str,
    max_attempts: int,
    shape: str,
    log_prefix: str = "",
) -> tuple[object | None, str | None]:
    result, error = parse(response)

    for attempt in range(1, max_attempts + 1):
        if result is not None:
            return result, None

        logger.warning(
            f"{log_prefix}repair {attempt}/{max_attempts}: {str(error).replace(chr(10), ' | ')}"
        )
        progress.emit(
            "repair",
            attempt=attempt,
            max_attempts=max_attempts,
            error=str(error)[:300],
            where=log_prefix.strip() or shape,
        )
        prompt = json_repair_prompt(
            broken_output=response, error_msg=error or "invalid JSON", shape=shape
        )
        response = inference.generate(model=repair_model, prompt=prompt).response
        result, error = parse(response)

    return result, error
