from collections.abc import Callable

from ..variant_generator import GeneratedVariant
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
    counts: dict[str, int] = {}
    for item in bank.values():
        for concept in item.get("concepts") or []:
            counts[concept] = counts.get(concept, 0) + 1
    return sorted(counts, key=lambda c: counts[c], reverse=True)[:k]
