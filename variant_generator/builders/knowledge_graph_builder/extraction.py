"""Phase 1 — corpus to a raw inventory of concepts and relation triples.

Linking is NOT done here: it used to run over the raw inventory, where the same idea is
still present under several names, and every relation whose endpoint was later merged or
dropped was thrown away by `apply_node_map`. It runs in `curation` now, once the names are
canonical and the domains exist to break the question into pieces.
"""

from collections import Counter, defaultdict
from pathlib import Path

from loguru import logger

from ... import config, inference, progress
from ...prompts import extract_typed_graph_prompt
from .. import _source_docs
from . import parsing
from .schemas import EXTRACT_SCHEMA


def run(
    input_dir: str | Path,
    *,
    converter,
    schema,
    chunk_size: int,
    markdown_cache_dir: Path,
    max_attempts: int,
    recursive: bool = False,
) -> dict:
    documents = convert_corpus(
        input_dir,
        recursive=recursive,
        converter=converter,
        chunk_size=chunk_size,
        markdown_cache_dir=markdown_cache_dir,
    )
    if not documents:
        return {}

    origins, relations = extract_documents(
        documents, schema=schema, max_attempts=max_attempts
    )
    if not origins:
        logger.error("Ningún concepto extraído del corpus")
        return {}

    staging = assemble(origins, relations, documents)
    logger.success(
        f"Extracción terminada: {len(staging['entities'])} concepto(s), "
        f"{len(staging['relations'])} relación(es)"
    )
    return staging


# Every document is converted and chunked up front so the extraction bar knows its
# own total: a per-file bar cannot say how much of the corpus is left, because a
# 40-chunk lecture and a 3-chunk one weigh the same in it.
def convert_corpus(
    input_dir: str | Path,
    *,
    recursive: bool,
    converter,
    chunk_size: int,
    markdown_cache_dir: Path,
) -> list[tuple[str, list[str], list[tuple[str, str]]]]:
    files = _source_docs.list_source_files(input_dir, recursive=recursive)
    if not files:
        logger.error(f"Ningún documento admitido en {input_dir}")
        return []

    logger.info(f"{len(files)} documento(s) en el corpus; convirtiendo a markdown")
    progress.phase("convert", f"0/{len(files)} documento(s)")

    converted: list[tuple[str, dict[int, list[str]], list[tuple[str, str]]]] = []
    with progress.step(
        "kg_convert", "Convirtiendo los documentos del corpus", len(files)
    ) as reporter:
        for idx, file_path in enumerate(files, 1):
            progress.checkpoint()
            reporter.tick(idx, detail=file_path.name)
            progress.advance((idx - 1) / len(files), f"{file_path.name} ({idx}/{len(files)})")
            try:
                text = _source_docs.to_markdown(
                    converter, file_path, cache_dir=markdown_cache_dir
                )
            except progress.Cancelled:
                raise
            except Exception as e:
                logger.exception(f"[{file_path.name}] omitido: {e}")
                continue

            chunks = _source_docs.chunk_markdown(text, chunk_size)
            if not chunks:
                logger.warning(f"[{file_path.name}] no produjo texto")
                continue
            converted.append((file_path.name, _source_docs.headings_by_level(text), chunks))

    titles = select_titles([levels for _, levels, _ in converted])
    documents = [
        (name, titles[idx], chunks) for idx, (name, _, chunks) in enumerate(converted)
    ]
    for name, doc_titles, _ in documents:
        logger.debug(f"[{name}] título(s): {' · '.join(doc_titles) or '—'}")

    progress.advance(1.0, f"{len(documents)} documento(s) listos")
    return documents


def select_titles(levels_per_doc: list[dict[int, list[str]]]) -> list[list[str]]:
    total = len(levels_per_doc)
    seen = Counter()
    for levels in levels_per_doc:
        for titles in levels.values():
            seen.update({t.casefold() for t in titles})

    selected = []
    for levels in levels_per_doc:
        chosen: list[str] = []
        for level in sorted(levels):
            kept = [
                t
                for t in levels[level]
                if total < 2 or seen[t.casefold()] / total <= config.KG_BUILDER_TITLE_UBIQUITY
            ]
            if kept:
                chosen = kept[: config.KG_BUILDER_MAX_TITLES_PER_DOC]
                break
        selected.append(chosen)
    return selected


def extract_documents(
    documents: list[tuple[str, list[str], list[tuple[str, str]]]],
    *,
    schema,
    max_attempts: int,
) -> tuple[dict[str, set[int]], set[tuple[str, str, str]]]:
    total = sum(len(chunks) for _, _, chunks in documents)
    logger.info(f"Extrayendo de {total} fragmento(s) de {len(documents)} documento(s)")
    progress.phase("extract", f"0/{total} fragmento(s)")

    origins: dict[str, set[int]] = defaultdict(set)
    relations: set[tuple[str, str, str]] = set()
    done = 0

    with progress.step("kg_extract", "Extrayendo conceptos y relaciones", total) as reporter:
        for di, (name, _, chunks) in enumerate(documents):
            for ci, (location, chunk) in enumerate(chunks, 1):
                progress.checkpoint()
                done += 1
                reporter.tick(
                    done,
                    detail=(
                        f"{name} · {location or f'fragmento {ci}'} · "
                        f"{len(origins)} concepto(s), {len(relations)} relación(es)"
                    ),
                )
                progress.advance(
                    (done - 1) / total,
                    f"fragmento {done}/{total} · {len(origins)} concepto(s)",
                )
                tag = f"[{name} · chunk {ci}/{len(chunks)}] "
                chunk_concepts, chunk_relations = extract_from_chunk(
                    chunk, tag, location, schema=schema, max_attempts=max_attempts
                )
                for concept in chunk_concepts:
                    origins[concept].add(di)
                for source, _key, target in chunk_relations:
                    origins[source].add(di)
                    origins[target].add(di)
                relations.update(tuple(r) for r in chunk_relations)
                progress.emit(
                    "artifact.progress",
                    name="knowledge_graph",
                    count=len(origins),
                    detail=f"{len(relations)} relación(es)",
                )

    progress.advance(1.0, f"{len(origins)} concepto(s), {len(relations)} relación(es)")
    return dict(origins), relations


# The only per-chunk call of the build, so the only one that stays without reasoning:
# every other model call here happens a handful of times and can afford to think.
def extract_from_chunk(
    chunk: str,
    log_prefix: str,
    location: str = "",
    *,
    schema,
    max_attempts: int,
) -> tuple[list[str], list[list[str]]]:
    prompt = extract_typed_graph_prompt(chunk, schema, location)
    response = inference.generate(
        model=config.KG_EXTRACT_MODEL, prompt=prompt, think=False, format=EXTRACT_SCHEMA
    ).response
    raw = parsing.parse_object(response, log_prefix, EXTRACT_SCHEMA, max_attempts)
    if raw is None:
        return [], []
    concepts = [c.strip() for c in raw.get("concepts", []) if isinstance(c, str) and c.strip()]
    relations = parsing.valid_relations(raw.get("relations", []), schema, allowed=None)
    return concepts, relations


# Concepts and relations are collected into SETS across the whole corpus, so a concept seen
# in twenty chunks costs one entry and no frequency signal survives. Rarity is not evidence
# of noise here — `cleaning` is told explicitly not to drop a term for being infrequent.
def assemble(
    origins: dict[str, set[int]],
    relations: set[tuple[str, str, str]],
    documents: list[tuple[str, list[str], list[tuple[str, str]]]],
) -> dict:
    rels = sorted(list(r) for r in relations)
    return {
        "entities": sorted(origins),
        "edges": sorted({r[1] for r in rels}),
        "relations": rels,
        "documents": [{"name": name, "titles": titles} for name, titles, _ in documents],
        "origins": {name: sorted(origins[name]) for name in sorted(origins)},
    }
