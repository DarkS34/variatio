from loguru import logger

from . import config, inference, progress
from .builders.knowledge_graph_builder import blocks, parsing
from .content_context import ContentContext
from .builders.knowledge_graph_builder.schemas import TAGGABLE_SCHEMA
from .prompts import review_taggable_concepts_prompt

MAX_SAMPLES_PER_DOMAIN = 3
SAMPLE_CHARS = 300

BUILD_PHASES = (("taggable", "Revisando qué conceptos sirven como etiqueta", 100),)


def modalities_block(exemplars_profile) -> str:
    lines = []
    for item_type in exemplars_profile.item_types.values():
        line = f"- **{item_type.label}** (`{item_type.key}`)"
        if item_type.description:
            line += f": {item_type.description}"
        lines.append(line)
    return "\n".join(lines)


def samples_block(exemplars_profile, exemplars_bank, domain_concepts: list[str]) -> str:
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
    exemplars_bank: dict | None = None,
    content_context: ContentContext | None = None,
    max_attempts: int = config.MAX_JSON_REPAIR_TRIES,
) -> list[str]:
    content_context = content_context or ContentContext()
    domains = list(knowledge_graph.concepts_by_domains)
    if not domains:
        return []

    relations = _relation_triples(knowledge_graph)
    modalities = modalities_block(exemplars_profile)
    logger.info(
        f"Revisando la etiquetabilidad de {len(domains)} dominio(s) contra "
        f"{len(exemplars_profile.item_types)} modalidad(es) del perfil"
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
                    exemplars_bank,
                    content_context,
                    modalities,
                    max_attempts,
                )
            )

    logger.success(
        f"Etiquetabilidad: {len(non_taggable)} concepto(s) excluidos de "
        f"{sum(len(m) for m in knowledge_graph.concepts_by_domains.values())}"
    )
    progress.advance(1.0, f"{len(non_taggable)} concepto(s) no etiquetables")
    return sorted(non_taggable)


def _relation_triples(knowledge_graph) -> list[list]:
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
    exemplars_bank,
    content_context,
    modalities,
    max_attempts,
) -> list[str]:
    prompt = review_taggable_concepts_prompt(
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
        think=True,
        temperature=config.TEMPERATURE_REASONING,
    ).response
    raw = (
        parsing.parse_object(
            response, f"[taggable · {domain}] ", TAGGABLE_SCHEMA, max_attempts
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
            logger.debug(f"[{domain}] «{concept}» no sirve como etiqueta: {reason}")
    return excluded
