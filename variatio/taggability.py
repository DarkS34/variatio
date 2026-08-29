"""Which concepts of the graph are any use as a LABEL for this instance's items.

Taggability is not a property of the graph: a concept is useless as a label only relative
to the shapes of item the exemplars profile declares, so the review is made per domain
against the profile's modalities and real statements from the bank. It imports the KG
builder's prompt blocks because the review left the build and kept its prompt — a second
copy of the renderers would desynchronise this block format from the graph's own.
"""

from loguru import logger

from . import config
from .builders.knowledge_graph_builder import blocks, parsing
from .builders.knowledge_graph_builder.schemas import TAGGABLE_SCHEMA
from .core import inference, progress
from .instance.content_context import ContentContext

MAX_SAMPLES_PER_DOMAIN = 3
SAMPLE_CHARS = 300

BUILD_PHASES = (("taggable", "Revisando qué conceptos sirven como etiqueta", 100),)


def modalities_block(exemplars_profile) -> str:
    """Render the profile's modalities for the prompt."""
    lines = []
    for item_type in exemplars_profile.item_types.values():
        line = f"- **{item_type.label}** (`{item_type.key}`)"
        if item_type.description:
            line += f": {item_type.description}"
        lines.append(line)
    return "\n".join(lines)


def samples_block(exemplars_profile, exemplars_bank, domain_concepts: list[str]) -> str:
    """Render up to `MAX_SAMPLES_PER_DOMAIN` real statements touching this domain."""
    if not exemplars_bank:
        return ""
    wanted = set(domain_concepts)
    lines = []
    for item in exemplars_bank.values():
        if len(lines) >= MAX_SAMPLES_PER_DOMAIN:
            break
        if not wanted.intersection(item.get("concepts") or []):
            continue
        key = item.get("item_type")
        item_type = exemplars_profile.item_types.get(key) if key else None
        field = item_type.primary_field if item_type else "statement"
        text = " ".join(str(item.get(field) or "").split())[:SAMPLE_CHARS]
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines)


def review(
    knowledge_graph,
    exemplars_profile,
    prompts,
    exemplars_bank: dict | None = None,
    content_context: ContentContext | None = None,
    max_attempts: int | None = None,
) -> list[str]:
    """Return the concepts that are no use as labels, judged one domain at a time.

    Empty when the graph declares no domains. Per domain rather than over the whole
    inventory because the judgement is a comparison among siblings.
    """
    if max_attempts is None:
        max_attempts = config.MAX_JSON_REPAIR_TRIES
    content_context = content_context or ContentContext()
    domains = list(knowledge_graph.concepts_by_domains)
    if not domains:
        return []

    relations = _relation_triples(knowledge_graph)
    modalities = modalities_block(exemplars_profile)
    logger.info(
        f"Reviewing taggability across {len(domains)} domain(s) against "
        f"{len(exemplars_profile.item_types)} modality(ies) of the profile"
    )

    non_taggable: set[str] = set()
    with progress.step(
        "taggability", "Revisando qué conceptos sirven como etiqueta", len(domains)
    ) as reporter:
        for idx, domain in enumerate(domains, 1):
            progress.checkpoint()
            members = knowledge_graph.concepts_by_domains[domain]
            reporter.tick(idx, detail=f"{domain} · {len(members)} concepto(s)")
            progress.advance((idx - 1) / len(domains), f"{domain} ({idx}/{len(domains)})")
            non_taggable.update(
                _judge_domain(
                    domain,
                    members,
                    domains,
                    relations,
                    exemplars_profile,
                    prompts,
                    exemplars_bank,
                    content_context,
                    modalities,
                    max_attempts,
                )
            )

    logger.success(
        f"Taggability: {len(non_taggable)} concept(s) excluded out of "
        f"{sum(len(m) for m in knowledge_graph.concepts_by_domains.values())}"
    )
    progress.advance(1.0, f"{len(non_taggable)} concepto(s) no etiquetables")
    return sorted(non_taggable)


def _relation_triples(knowledge_graph) -> list[list]:
    """Flatten every relation of the graph into `[source, verb, target]` triples."""
    triples = []
    for verbose, graph in knowledge_graph.graphs.items():
        for source, target in graph.edges():
            triples.append([source, verbose, target])
    return triples


def _judge_domain(
    domain,
    members,
    domains,
    relations,
    exemplars_profile,
    prompts,
    exemplars_bank,
    content_context,
    modalities,
    max_attempts,
) -> list[str]:
    """Ask the model which of one domain's concepts are no use as labels.

    Only names the domain actually holds survive, so an invented one is dropped. A
    bare list is accepted as well as the documented `{concept: reason}` map.
    """
    prompt = prompts.review_taggable_concepts_prompt(
        domain,
        blocks.concepts_block(domains),
        blocks.nodes_block(members, relations, {}),
        content_context.prompt_block(),
        modalities,
        samples_block(exemplars_profile, exemplars_bank, members),
    )
    response = inference.generate(
        model=config.KG_TAGGABLE_MODEL,
        prompt=prompt,
        think=config.THINK_KG_TAGGABLE,
        temperature=inference.judgement_temperature(config.THINK_KG_TAGGABLE),
    ).response
    raw = (
        parsing.parse_object(
            response, f"[taggable · {domain}] ", TAGGABLE_SCHEMA, max_attempts, prompts
        )
        or {}
    )
    verdicts = raw.get("non_taggable") or {}
    if isinstance(verdicts, list):
        verdicts = {c: "" for c in verdicts if isinstance(c, str)}
    if not isinstance(verdicts, dict):
        return []

    valid = set(members)
    excluded = []
    for concept, reason in verdicts.items():
        if concept in valid:
            excluded.append(concept)
            logger.debug(f"[{domain}] «{concept}» is no use as a label: {reason}")
    return excluded
