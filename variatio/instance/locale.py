"""The workspace's own language: which prompt set and relation vocabulary it is built with.

`instance/locale.json` is undotted because it travels with `export-instance`; the database
column beside it is a mirror, so the panel can list without touching disk. A workspace's
language is chosen at creation and never after — the relation `verbose` labels are written
into `knowledge_graph.json` and the loader indexes by them.
"""

import json

from loguru import logger

from .. import prompts
from ..core import languages
from ..core.json_io import write_json
from ..core.workspace import Workspace
from . import relations

PROMPT_LANGUAGE_KEY = "prompt_language"


def prompt_language(ws: Workspace) -> str:
    """Return the language this workspace's prompts are written in.

    Tolerant on the way out: an unreadable or unknown value warns and falls back to the
    default, because a corrupt config file must never stop the process starting.
    """
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
    """Write the workspace's prompt language, refusing an unknown one."""
    problem = languages.error(language)
    if problem:
        raise ValueError(problem)
    resolved = languages.normalise(language)
    write_json(ws.locale_path, {PROMPT_LANGUAGE_KEY: resolved})
    return resolved


def relation_schema(ws: Workspace):
    """Return the relation vocabulary that goes with this workspace's prompts.

    Resolved here so no caller pairs a schema with a prompt set of the other language: the
    catalogue's definitions and slot names are prose the prompts interpolate.
    """
    return relations.schema_for(prompt_language(ws))


def prerequisite_relation(ws: Workspace) -> str | None:
    """Return the verbose label of the relation that orders the curriculum."""
    return relation_schema(ws).prerequisite_verbose


def difficulty(ws: Workspace) -> tuple[str, list[str]]:
    """Return the difficulty field name and its rungs, as this workspace's prompts write them.

    Resolved here for the same reason as the relation vocabulary: the field NAME is prose
    the prompt set owns — `nivel_dificultad` in Spanish, `difficulty_level` in English — so
    a caller that writes one must not pair it with the other set's ladder.
    """
    module = prompts.of(prompt_language(ws))
    return module.DIFFICULTY_FIELD, list(module.DIFFICULTY_LEVELS)
