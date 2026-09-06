"""Phase 2 — generating variants from an initialised pipeline context."""

from collections.abc import Callable

from .. import config
from ..runtime.generator import GeneratedVariant
from .initialize import RuntimeContext


class UnofferedModelError(ValueError):
    """A commission named a model the installation does not offer for generation."""


def generate(
    context: RuntimeContext,
    concepts: list[str] | None = None,
    item_type: str | None = None,
    n: int = 1,
    fixed: dict[str, object] | None = None,
    curriculum: list[str] | None = None,
    instructions: str | None = None,
    think: bool | str = True,
    model: str | None = None,
    avoid: list[str] | None = None,
    on_accepted: Callable[[GeneratedVariant, int], None] | None = None,
) -> list[GeneratedVariant]:
    """Generate `n` variants, defaulting to the bank's most frequent concepts.

    `curriculum` is passed through as it arrives, the empty list included — the server
    resolves a workspace's own before calling, because a run has to record the curriculum
    that ran and not the one that was asked for. `model` is resolved the same way, and
    for the same reason: what is stored beside an item has to be what wrote it.
    """
    targets = concepts or _top_tagged_concepts(context.exemplars_bank, n)
    if not targets:
        raise ValueError(
            "No target concepts: none were given and the exemplars bank has no tagged concepts"
        )
    writer = resolve_generation_model(model)
    return context.generator.generate(
        concepts=targets,
        item_type=item_type,
        n=n,
        fixed=fixed,
        curriculum=curriculum,
        instructions=instructions,
        think=resolve_generation_effort(writer, think),
        model=writer,
        avoid=avoid,
        on_accepted=on_accepted,
    )


def _top_tagged_concepts(bank: dict, k: int) -> list[str]:
    """Return the k concepts the bank tags most often."""
    counts: dict[str, int] = {}
    for item in bank.values():
        for concept in item.get("concepts") or []:
            counts[concept] = counts.get(concept, 0) + 1
    return sorted(counts, key=lambda c: counts[c], reverse=True)[:k]


def resolve_generation_model(requested: str | None) -> str:
    """Return the model a commission will be written with, or raise if it is not offered.

    Absent means the first offered one, which is what `VARIANT_GENERATION_LLM` already
    resolves to. A name that IS given is checked rather than trusted: the offered list is
    edited from the panel while the process runs, so a job queued under one list can
    perfectly well reach its handler under another.
    """
    offered = generation_models()
    if not requested:
        return offered[0]
    if requested not in offered:
        raise UnofferedModelError(
            f"El modelo «{requested}» no está entre los que ofrece esta instalación "
            f"({', '.join(offered)})."
        )
    return requested


def generation_models() -> list[str]:
    """Return the models a commission may choose from, the default one first."""
    return [str(model) for model in config.GENERATION_MODELS]


def resolve_generation_effort(model: str, think: bool | str) -> bool | str:
    """Return the reasoning a commission actually runs with, once the model is known.

    A model whose effort the installation has locked is not the requester's to adjust, so
    whatever arrived is replaced by the declared level — and by `True` when none is
    declared, which is the engine's own default and what the lock has always promised. It
    is idempotent, so the handler may resolve it for its log line and `generate` again for
    the call without the two being able to disagree. Reasoning switched OFF is left alone:
    the lock is about how much, never about whether.
    """
    if not think or model not in fixed_effort_models():
        return think
    return fixed_effort_levels().get(model) or True


def fixed_effort_models() -> list[str]:
    """Return the offered models whose reasoning effort may not be adjusted per commission.

    A separate list rather than a shape inside `generation.models`, so that removing a model
    from the offer for an afternoon does not throw away a measurement of how it reasons.
    Nothing here reads it: it travels to the browser, which draws or withholds one slider.
    """
    return [str(model) for model in config.FIXED_EFFORT_MODELS]


def fixed_effort_levels() -> dict[str, str]:
    """Return the level each locked model is called with, by model name.

    Only the names in `fixed_effort_models()` are read from it; one that is not locked is
    kept and ignored, so taking the lock off for an afternoon does not lose the level.
    """
    return {str(model): str(level) for model, level in config.FIXED_EFFORT_LEVELS.items()}
