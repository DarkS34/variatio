import json

from loguru import logger

from . import config, inference


def prepare_models() -> None:
    all_models = [
        config.CONTENT_CLEANING_LLM,
        config.CONTENT_FORMATTING_LLM,
        config.EMBEDDING_LLM,
        config.CONCEPT_TAGGER_LLM,
        config.REPAIR_LLM,
        config.CONTENT_GENERATION_LLM,
        config.KG_BUILDER_LLM,
    ]

    logger.info(f"Initializing models on '{inference.engine_name()}' engine")
    failed = [m for m in all_models if not inference.ensure_model(m)]
    if failed:
        raise RuntimeError(f"Failed to install model(s): {', '.join(failed)}")

    for m in set(all_models):
        inference.warmup(m, is_embedding=(m == config.EMBEDDING_LLM))

    logger.success("All models loaded")


def json_repair(
    broken_json: str, repair_model: str = config.REPAIR_LLM, error: str = "", max_attempts: int = 5
):
    from .prompts import json_repair as _repair_prompt

    response = inference.generate(
        model=repair_model, prompt=_repair_prompt(broken_json, error or "invalid JSON")
    ).response

    for attempt in range(1, max_attempts + 1):
        try:
            result = json.loads(response)
            logger.info(f"JSON repaired in {attempt} attempt(s)")
            return result
        except json.JSONDecodeError as parse_err:
            if attempt < max_attempts:
                logger.debug(f"Repair attempt {attempt}/{max_attempts} failed: {parse_err}")
                response = inference.generate(
                    model=repair_model,
                    prompt=f"Invalid JSON — {parse_err}. Return only valid JSON:\n\n{response}",
                ).response

    logger.warning("Failed to repair JSON, returning empty list")
    return []
