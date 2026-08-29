"""Phase 2 — generating variants from an initialised pipeline context."""

from collections.abc import Callable

from ..variatio import GeneratedVariant
from .initialize import PipelineContext


def generate(
    context: PipelineContext,
    concepts: list[str] | None = None,
    item_type: str | None = None,
    n: int = 1,
    fixed: dict[str, object] | None = None,
    curriculum: list[str] | None = None,
    instructions: str | None = None,
    think: bool | str = True,
    avoid: list[str] | None = None,
    on_accepted: Callable[[GeneratedVariant, int], None] | None = None,
) -> list[GeneratedVariant]:
    """Generate `n` variants, defaulting to the bank's most frequent concepts.

    `curriculum` is passed through as it arrives, the empty list included — the server
    resolves a workspace's own before calling, because a run has to record the curriculum
    that ran and not the one that was asked for.
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
