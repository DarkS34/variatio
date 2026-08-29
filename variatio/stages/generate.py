"""Phase 2 — generating variants from an initialised pipeline context."""

from collections.abc import Callable

from .. import config
from ..variatio import GeneratedVariant
from .initialize import PipelineContext


class UnofferedModelError(ValueError):
    """A commission named a model the installation does not offer for generation."""


def generation_models() -> list[str]:
    """Return the models a commission may choose from, the default one first."""
    return [str(model) for model in config.GENERATION_MODELS]


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


def generate(
    context: PipelineContext,
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
    return context.generator.generate(
        concepts=targets,
        item_type=item_type,
        n=n,
        fixed=fixed,
        curriculum=curriculum,
        instructions=instructions,
        think=think,
        model=resolve_generation_model(model),
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
