import json

from loguru import logger

from ..core import languages
from ..core.json_io import write_json
from ..core.workspace import Workspace
from . import relations

PROMPT_LANGUAGE_KEY = "prompt_language"


def prompt_language(ws: Workspace) -> str:
    path = ws.locale_path
    if not path.is_file():
        return languages.DEFAULT
    try:
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"[locale] Could not read '{path}': {exc}; using «{languages.DEFAULT}»")
        return languages.DEFAULT
    stored = raw.get(PROMPT_LANGUAGE_KEY) if isinstance(raw, dict) else None
    resolved = languages.normalise(stored)
    if resolved is None:
        logger.warning(
            f"[locale] «{stored}» is not a known language in '{path}'; "
            f"using «{languages.DEFAULT}»"
        )
        return languages.DEFAULT
    return resolved


def set_prompt_language(ws: Workspace, language: str) -> str:
    problem = languages.error(language)
    if problem:
        raise ValueError(problem)
    resolved = languages.normalise(language)
    write_json(ws.locale_path, {PROMPT_LANGUAGE_KEY: resolved})
    return resolved


# What follows from the language, resolved here so no caller pairs a schema with a prompt
# set of the other language by hand. The prompts interpolate `catalog_block()`, whose
# definitions and slot names are prose: the two have to come from the same workspace.
def relation_schema(ws: Workspace):
    return relations.schema_for(prompt_language(ws))


def prerequisite_relation(ws: Workspace) -> str | None:
    return relation_schema(ws).prerequisite_verbose
