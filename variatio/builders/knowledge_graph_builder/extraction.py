"""Phase 1 — corpus to a raw inventory of concepts and relation triples.

Linking is NOT done here. Over the raw inventory the same idea is still present under
several names, and every relation whose endpoint was later merged or dropped was thrown
away by `apply_node_map`; it runs in `curation`, once the names are canonical and the
domains exist to break the question into pieces.
"""

import re
from collections import Counter, defaultdict
from pathlib import Path

from loguru import logger

from ... import config
from ...core import inference, progress
from ...core.lexicon import mentions
from .. import source_docs
from . import parsing
from .schemas import EXTRACT_SCHEMA


def run(
    input_dir: str | Path,
    *,
    converter,
    schema,
    chunk_size: int,
    cache_dir: Path,
    max_attempts: int,
    prompts,
    recursive: bool = False,
) -> dict:
    """Convert, chunk and read the whole corpus, returning the staging inventory."""
    documents = convert_corpus(
        input_dir,
        recursive=recursive,
        converter=converter,
        chunk_size=chunk_size,
        cache_dir=cache_dir,
        prompts=prompts,
    )
    if not documents:
        return {}

    found = extract_documents(
        documents, schema=schema, max_attempts=max_attempts, prompts=prompts
    )
    if not found["origins"]:
        logger.error("No concept extracted from the corpus")
        return {}

    staging = assemble(found, documents)
    logger.success(
        f"Extraction finished: {len(staging['entities'])} concept(s), "
        f"{len(staging['relations'])} relation(s)"
    )
    return staging


def convert_corpus(
    input_dir: str | Path,
    *,
    recursive: bool,
    converter,
    chunk_size: int,
    cache_dir: Path,
    prompts,
) -> list[tuple[str, list[str], list[tuple[str, list[str], str]]]]:
    """Transcribe and chunk every document up front, as `(name, titles, chunks)`.

    Up front and not per file, so the extraction bar knows its own total: a 40-chunk lecture
    and a 3-chunk one weigh the same in a per-file bar. The corpus takes the same
    page-transcription route as the two exemplars builders — one engine and one algorithm
    for both raw slots — so Docling is left with the Office files, which have no page to
    render and whose pictures are read one by one with the same model.
    """
    files = source_docs.list_source_files(input_dir, recursive=recursive)
    if not files:
        logger.error(f"No supported document in {input_dir}")
        return []

    logger.info(f"{len(files)} document(s) in the corpus; transcribing to markdown")
    progress.phase("convert", f"0/{len(files)} documento(s)")

    converted: list[tuple[str, dict[int, list[str]], list[tuple[str, list[str], str]]]] = []
    with progress.step(
        "kg_convert", "Reading the corpus documents", len(files)
    ) as reporter:
        for idx, file_path in enumerate(files, 1):
            progress.checkpoint()
            reporter.start(idx, detail=file_path.name)
            progress.advance((idx - 1) / len(files), f"{file_path.name} ({idx}/{len(files)})")
            try:
                text = source_docs.document_markdown(
                    file_path,
                    prompts,
                    converter=converter,
                    tag=f"[{idx}/{len(files)}] ",
                    cache_dir=cache_dir,
                )
            except progress.Cancelled:
                raise
            except Exception as e:
                logger.exception(f"[{file_path.name}] skipped: {e}")
                continue

            chunks = source_docs.chunk_sections(text, chunk_size)
            if not chunks:
                logger.warning(f"[{file_path.name}] produced no text")
                continue
            converted.append((file_path.name, source_docs.headings_by_level(text), chunks))

    titles = select_titles([levels for _, levels, _ in converted])
    documents = [
        (name, titles[idx], chunks) for idx, (name, _, chunks) in enumerate(converted)
    ]
    for name, doc_titles, _ in documents:
        logger.debug(f"[{name}] title(s): {' · '.join(doc_titles) or '—'}")

    progress.advance(1.0, f"{len(documents)} documento(s) listos")
    return documents


def select_titles(levels_per_doc: list[dict[int, list[str]]]) -> list[list[str]]:
    """Name each document by its shallowest headings, dropping the ones every file repeats."""
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
    documents: list[tuple[str, list[str], list[tuple[str, list[str], str]]]],
    *,
    schema,
    max_attempts: int,
    prompts,
) -> dict:
    """Read every chunk of the corpus, gathering concepts, relations and their evidence."""
    total = sum(len(chunks) for _, _, chunks in documents)
    logger.info(f"Extracting from {total} chunk(s) of {len(documents)} document(s)")
    progress.phase("extract", f"0/{total} fragmento(s)")

    origins: dict[str, set[int]] = defaultdict(set)
    passages: dict[str, list[dict]] = defaultdict(list)
    positions: dict[str, int] = {}
    occurrences: dict[str, list[int]] = defaultdict(list)
    outline: list[dict] = []
    definitions: dict[str, str] = {}
    relations: set[tuple[str, str, str]] = set()
    done = 0

    with progress.step("kg_extract", "Extracting concepts and relations", total) as reporter:
        for di, (name, _, chunks) in enumerate(documents):
            for ci, (location, headings, chunk) in enumerate(chunks, 1):
                progress.checkpoint()
                done += 1
                for heading in headings:
                    outline.append({"document": di, "heading": heading, "chunk": done})
                reporter.start(
                    done,
                    detail=(
                        f"{name} · {location or f'fragmento {ci}'} · "
                        f"{len(origins)} concept(s), {len(relations)} relation(s)"
                    ),
                )
                progress.advance(
                    (done - 1) / total,
                    f"fragmento {done}/{total} · {len(origins)} concepto(s)",
                )
                tag = f"[{name} · chunk {ci}/{len(chunks)}] "
                chunk_concepts, chunk_relations, chunk_definitions = extract_from_chunk(
                    chunk, tag, location, schema=schema, max_attempts=max_attempts,
            prompts=prompts,
                )
                chunk_concepts, chunk_relations, chunk_definitions = glean_chunk(
                    chunk,
                    tag,
                    location,
                    chunk_concepts,
                    chunk_relations,
                    chunk_definitions,
                    schema=schema,
                    max_attempts=max_attempts,
            prompts=prompts,
                )
                seen_here = set(chunk_concepts)
                for source, _key, target in chunk_relations:
                    seen_here.update((source, target))
                for concept in sorted(seen_here):
                    origins[concept].add(di)
                    positions.setdefault(concept, done)
                for concept in sorted(set(chunk_concepts)):
                    occurrences[concept].append(done)
                    remember_passage(passages[concept], concept, chunk, name, location)
                    if concept not in definitions and chunk_definitions.get(concept):
                        definitions[concept] = chunk_definitions[concept]
                relations.update(tuple(r) for r in chunk_relations)
                progress.emit(
                    "artifact.progress",
                    name="knowledge_graph",
                    count=len(origins),
                    detail=f"{len(relations)} relation(s)",
                )

    progress.advance(1.0, f"{len(origins)} concept(s), {len(relations)} relation(s)")
    return {
        "origins": dict(origins),
        "passages": dict(passages),
        "positions": positions,
        "occurrences": dict(occurrences),
        "outline": outline,
        "definitions": definitions,
        "relations": relations,
    }


# CORPUS ANCHORING ------------------------------------------------------------------------
#
# A concept of the graph is what a model said it read; the passage is what was actually
# read. Keeping them together is what allows showing where each node comes from, and it
# is what `concept_description_prompt` uses to describe with the syllabus's vocabulary
# instead of whatever the model has at hand.


def remember_passage(
    stored: list[dict], concept: str, chunk: str, document: str, location: str
) -> None:
    """Record one more corpus passage for a concept, up to the cap and never a duplicate."""
    if len(stored) >= config.KG_MAX_SOURCE_PASSAGES:
        return
    text = excerpt(chunk, concept, config.KG_SOURCE_PASSAGE_CHARS)
    if not text or any(entry["text"] == text for entry in stored):
        return
    stored.append({"document": document, "location": location, "text": text})


_LEADER = re.compile(r"\.{4,}|·{4,}|…{2,}")
_SENTENCE_END = re.compile(r"[.!?:](?=\s|$)")
MIN_LEADER_RUNS = 3


def is_navigation(paragraph: str) -> bool:
    """Say whether a paragraph is a table of contents rather than material.

    It keys on DOT-LEADER RUNS and not on punctuation density or line length, which mis-fire
    on real prose; three runs is what separates an index from a sentence with an ellipsis.
    """
    if not paragraph.strip():
        return True
    return len(_LEADER.findall(paragraph)) >= MIN_LEADER_RUNS


def clip_to_sentence(text: str, max_chars: int) -> str:
    """Cut `text` at the last sentence end within the budget, or at the last word."""
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    ends = [m.end() for m in _SENTENCE_END.finditer(window)]
    if ends:
        return window[: ends[-1]].strip()
    cut = window.rfind(" ")
    return window[:cut].strip() if cut > 0 else ""


def _grow_into_neighbours(text: str, paragraphs: list[str], hit: int, max_chars: int) -> str:
    """Extend the anchor paragraph into the ones around it while the budget allows."""
    before, after = hit - 1, hit + 1
    while before >= 0 or after < len(paragraphs):
        grown = False
        if after < len(paragraphs) and len(text) + len(paragraphs[after]) + 2 <= max_chars:
            text = f"{text}\n\n{paragraphs[after]}"
            after += 1
            grown = True
        if before >= 0 and len(text) + len(paragraphs[before]) + 2 <= max_chars:
            text = f"{paragraphs[before]}\n\n{text}"
            before -= 1
            grown = True
        if not grown:
            break
    return text


def excerpt(chunk: str, concept: str, max_chars: int) -> str:
    """The passage of `chunk` that justifies `concept`, cut by paragraphs and not by characters.

    Half a sentence quoted as proof that a concept exists in the material proves nothing,
    and the model reading it has to be able to understand it. When the name occurs in no
    non-navigation paragraph, NO passage is stored: a concept with no anchoring is honest
    and the interface already reports it, whereas quoting the head of the chunk anchored
    43 of 200 concepts to the table of contents.
    """
    paragraphs = [
        p
        for p in (p.strip() for p in re.split(r"\n\s*\n", chunk))
        if p and not is_navigation(p)
    ]
    if not paragraphs:
        return ""

    hit = next((i for i, p in enumerate(paragraphs) if mentions(p, concept)), None)
    if hit is None:
        return ""

    text = clip_to_sentence(paragraphs[hit], max_chars)
    if not text:
        return ""

    return _grow_into_neighbours(text, paragraphs, hit, max_chars).strip()




def extract_from_chunk(
    chunk: str,
    log_prefix: str,
    location: str = "",
    *,
    schema,
    max_attempts: int,
    prompts,
) -> tuple[list[str], list[list[str]], dict[str, str]]:
    """Read one chunk for concepts, definitions and relations.

    The only per-chunk call of the build, so the only one that stays without reasoning:
    every other model call here happens a handful of times and can afford to think.
    """
    prompt = prompts.extract_typed_graph_prompt(chunk, schema, location)
    return _ask(prompt, log_prefix, schema=schema, max_attempts=max_attempts, prompts=prompts)


def glean_chunk(
    chunk: str,
    log_prefix: str,
    location: str,
    concepts: list[str],
    relations: list[list[str]],
    definitions: dict[str, str],
    *,
    schema,
    max_attempts: int,
    prompts,
) -> tuple[list[str], list[list[str]], dict[str, str]]:
    """Read the same chunk again, shown what the first pass found, until nothing is added.

    A model asked to list everything lists the obvious and closes the JSON; asked instead
    «what is missing», with the inventory in front of it, it fills in the relations between
    concepts it already named, which is where the graph was thin.
    """
    if not concepts:
        return concepts, relations, definitions
    concepts = list(concepts)
    relations = list(relations)
    definitions = dict(definitions)
    for attempt in range(1, config.KG_EXTRACT_GLEANING_PASSES + 1):
        prompt = prompts.glean_typed_graph_prompt(
            chunk, schema, location, concepts, definitions, relations
        )
        more_concepts, more_relations, more_definitions = _ask(
            prompt, f"{log_prefix}[glean {attempt}] ", schema=schema, max_attempts=max_attempts,
            prompts=prompts,
        )
        known = set(concepts)
        new_concepts = [c for c in dict.fromkeys(more_concepts) if c not in known]
        known_relations = {tuple(r) for r in relations}
        new_relations = [r for r in more_relations if tuple(r) not in known_relations]
        if not new_concepts and not new_relations:
            break
        concepts.extend(new_concepts)
        relations.extend(new_relations)
        for name, definition in more_definitions.items():
            definitions.setdefault(name, definition)
        logger.debug(
            f"{log_prefix}second reading: +{len(new_concepts)} concept(s), "
            f"+{len(new_relations)} relation(s)"
        )
    return concepts, relations, definitions


def _ask(
    prompt: str, log_prefix: str, *, schema, max_attempts: int, prompts
) -> tuple[list[str], list[list[str]], dict[str, str]]:
    """Make one extraction call and read its answer, `([], [], {})` when it is unusable."""
    response = inference.generate(
        model=config.KG_EXTRACT_MODEL,
        prompt=prompt,
        think=config.THINK_KG_EXTRACT,
        format=None if config.THINK_KG_EXTRACT else EXTRACT_SCHEMA,
        temperature=inference.judgement_temperature(config.THINK_KG_EXTRACT),
    ).response
    raw = parsing.parse_object(response, log_prefix, EXTRACT_SCHEMA, max_attempts, prompts)
    if raw is None:
        return [], [], {}
    concepts, definitions = parsing.concepts_with_definitions(raw.get("concepts", []))
    relations = parsing.valid_relations(raw.get("relations", []), schema, allowed=None)
    return concepts, relations, definitions


def assemble(
    found: dict, documents: list[tuple[str, list[str], list[tuple[str, list[str], str]]]]
) -> dict:
    """Fold what every chunk found into the staging graph.

    Concepts and relations are collected into SETS across the whole corpus, so a concept
    seen in twenty chunks costs one entry and no frequency signal survives — rarity is not
    evidence of noise here, and `cleaning` is told explicitly not to drop a term for being
    infrequent. What DOES survive is where each concept was first seen and the definition
    written there: the material introduces a concept once, and both are read from there.
    """
    origins = found["origins"]
    rels = sorted(list(r) for r in found["relations"])
    names = sorted(origins)
    positions = found.get("positions") or {}
    occurrences = found.get("occurrences") or {}
    definitions = found.get("definitions") or {}
    return {
        "entities": names,
        "edges": sorted({r[1] for r in rels}),
        "relations": rels,
        "documents": [{"name": name, "titles": titles} for name, titles, _ in documents],
        "origins": {name: sorted(origins[name]) for name in names},
        "passages": {name: found["passages"].get(name, []) for name in names},
        "positions": {name: positions[name] for name in names if name in positions},
        "occurrences": {name: occurrences[name] for name in names if name in occurrences},
        "outline": found.get("outline") or [],
        "definitions": {name: definitions[name] for name in names if definitions.get(name)},
    }
