"""One repair loop for every component that has to parse a model's JSON."""

from collections.abc import Callable

from loguru import logger

from .. import config
from . import inference, progress


def parse_with_repair(
    response: str,
    parse: Callable[[str], tuple[object | None, str | None]],
    repair_model: str,
    max_attempts: int,
    shape: str,
    format: dict | str,
    prompts,
    log_prefix: str = "",
) -> tuple[object | None, str | None]:
    """Parse `response`, asking the repair model to fix it up to `max_attempts` times.

    `format` and `shape` are required rather than defaulted: a silent default is what let
    the tagger ask for an array while its parser demanded an object. The grammar is also
    what makes a SCHEMA error fixable at all — under it the model cannot name a field
    `sol` instead of `solucion`, which the prompt alone never prevented. Pass the schema
    when the caller has one, `"json"` when the shape is open-ended.

    `prompts` is the resolved prompt set of the workspace whose call is being repaired: a
    repair is one more turn of the same conversation, so asking in another language is how
    a reply comes back in one language and the artifact is written in another.
    """
    result, error = parse(response)

    for attempt in range(1, max_attempts + 1):
        if result is not None:
            return result, None

        logger.warning(
            f"{log_prefix}repair {attempt}/{max_attempts}: "
            f"{str(error).replace(chr(10), ' | ')}"
        )
        progress.emit(
            "repair",
            attempt=attempt,
            max_attempts=max_attempts,
            error=str(error)[:300],
            where=log_prefix.strip() or shape,
        )
        prompt = prompts.json_repair_prompt(
            broken_output=response, error_msg=error or "invalid JSON", shape=shape
        )
        response = inference.generate(
            model=repair_model,
            prompt=prompt,
            think=False,
            format=format,
            temperature=config.TEMPERATURE_REPAIR,
        ).response
        result, error = parse(response)

    return result, error
