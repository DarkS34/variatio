"""One engine's profile: the values of its engine-scoped settings, by their `config` names.

`config.json` keeps one settings section per engine (`profiles.<engine>`): the model of
every phase, the offered generation models, the context windows, the sampling and the
reasoning levels. Several engines serve at once — each person has one — so these values
cannot live in `config`, which holds one value per name for the whole installation. They
live here, resolved per engine, and every reader asks the profile of the engine its work
runs on: `settings.engine_profile().KG_EXTRACT_MODEL`.

Which engine that is, is the context's, as the engine itself is: `inference.using(engine)`
fixes both, and `use(name)` is what it calls. Reading with no engine fixed raises.
"""

import contextvars
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from .derived import PHASES
from .types import SettingError

# The derived `config` names that come from engine-scoped values. The named settings with
# `scope="engine"` are added by the caller from the registry.
DERIVED_NAMES = frozenset(
    {*PHASES.values(), "VARIANT_GENERATION_LLM", "LLM_CONTEXT", "SAMPLING", "EMBEDDING_MODELS"}
)

# A name, or a function that answers it the first time somebody asks: a request fixes its
# engine without knowing it yet, and only a route that reads a setting resolves it.
_engine: contextvars.ContextVar[str | Callable[[], str] | None] = contextvars.ContextVar(
    "settings_profile_engine", default=None
)


class Profile:
    """The resolved values of one engine's profile, read as attributes.

    Only the engine-scoped names are here: asking a profile for an installation setting
    (`OLLAMA_HOST`) is an `AttributeError`, not a silent read of the wrong layer.
    """

    def __init__(self, engine: str, values: dict[str, object]) -> None:
        """Hold `values` for `engine`."""
        self.engine = engine
        self.__dict__.update(values)


@contextmanager
def use(engine: str | Callable[[], str]) -> Iterator[None]:
    """Make `engine`'s profile the one this context reads, for the block.

    `engine` may be a function that names it, called when a setting is first read.
    """
    token = _engine.set(engine)
    try:
        yield
    finally:
        _engine.reset(token)


def current_engine() -> str:
    """The engine whose profile this context reads; raises when none is fixed."""
    engine = _engine.get()
    if engine is None:
        raise SettingError(
            "No hay perfil de motor activo: el proceso no fijó ningún motor para este trabajo"
        )
    return engine if isinstance(engine, str) else engine()
