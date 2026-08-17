from collections.abc import Callable

from loguru import logger

from . import config, inference, progress
from .prompts import json_repair_prompt


def prepare_models() -> None:
    all_models = sorted(
        {value for name, value in vars(config).items() if name.endswith("_LLM")}
    )

    ensure_models(all_models, "del pipeline")


def ensure_models(models: list[str], label: str) -> None:
    unique = list(dict.fromkeys(models))
    logger.info(f"Preparando los modelos {label}: {', '.join(unique)}")

    failed = [m for m in unique if not inference.ensure_model(m)]
    if failed:
        raise RuntimeError(f"No se pudieron instalar los modelos: {', '.join(failed)}")

    for m in unique:
        progress.checkpoint()
        inference.warmup(m, is_embedding=(m in config.EMBEDDING_MODELS))

    logger.success(f"Modelos {label} listos")


# `format` is required for the same reason `shape` is: a silent default is what let the
# tagger ask for an array while its parser demanded an object. It is what makes this loop
# able to fix a SCHEMA error at all — the prompt alone only ever asked for valid JSON, so a
# reply that parsed but named a field `sol` instead of `solucion` came back byte-identical
# three times in a row and burned the whole budget. Under the grammar that key cannot be
# written. Pass the schema when the caller has one, `"json"` when the shape is open-ended.
def parse_with_repair(
    response: str,
    parse: Callable[[str], tuple[object | None, str | None]],
    repair_model: str,
    max_attempts: int,
    shape: str,
    format: dict | str,
    log_prefix: str = "",
) -> tuple[object | None, str | None]:
    result, error = parse(response)

    for attempt in range(1, max_attempts + 1):
        if result is not None:
            return result, None

        logger.warning(
            f"{log_prefix}reparación {attempt}/{max_attempts}: "
            f"{str(error).replace(chr(10), ' | ')}"
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
        response = inference.generate(
            model=repair_model, prompt=prompt, think=False, format=format
        ).response
        result, error = parse(response)

    return result, error
