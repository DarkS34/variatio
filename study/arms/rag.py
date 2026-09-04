"""Arm 2 — the subject's own documents and a normal RAG. No graph, no bank, no profile.

This is the honest baseline: what a competent engineer builds with the teacher's PDFs and
none of this TFM. The `naive → rag` step measures what retrieving from the documents is
worth; the `rag → system` step measures what THE SYSTEM is worth on top of that — the
extraction of the bank, the profile, the tagging and the graph together — and that second
one is the contribution being defended.

What it retrieves over is `study.raw_text`: the raw slots read with a plain extractor
(pypdf and its Office twins), never the pipeline's vision transcription. Cut into pieces of
`RAG_CHUNK_CHARS`, embedded flat, searched by cosine, `RAG_TOP_K_THEORY` pieces of the
notes and `RAG_TOP_K_EXERCISES` of the exercise sheets handed over verbatim under a heading.

Same local model as the system arm (`commission.model`, the installation's
`evaluation.local_model`, defaulting to `VARIANT_GENERATION_LLM`) and the same reasoning
mode (`commission.effort`, drawn per session), so neither the model nor whether it
deliberated is a loose variable between them. Of the exemplars profile it receives the OUTPUT SHAPE and
nothing else (`output_schema`): no field descriptions, no difficulty criterion, no
`guidance`, no writing rules.
"""

import time

from loguru import logger

from variatio import config
from variatio.core import inference, progress
from variatio.core.repair import parse_with_repair
from variatio.stages.transcribe import CORPUS, EXEMPLARS
from variatio.variatio import parse_item

from .. import FAILED, OK, ArmResult, Commission, rag_index_path, raw_text
from .. import config as study_config
from .. import prompts as study_prompts
from .naive import build_prompt as build_naive_prompt
from .vector_store import FlatIndex

# Keyed by workspace and slot, not one global: with two instances in one process a single
# slot means one subject's documents answering the other's queries. The entries are compared
# inside the slot, because the documents also change while a workspace is alive.
_indices: dict[tuple[str, str], FlatIndex] = {}

_LABELS = {
    CORPUS: "Indexando los apuntes para la propuesta comparativa",
    EXEMPLARS: "Indexando los ejercicios para la propuesta comparativa",
}

# One step id per slot, because the client names a step by its id (`lib/names.ts`) and
# not by the label the server sends: under a shared id both indices read as one and the
# same row, and until 2026-09-04 that row still said «el banco».
_STEP_IDS = {
    CORPUS: "eval_rag_index_corpus",
    EXEMPLARS: "eval_rag_index_exemplars",
}


def index_for(ws, slot: str) -> FlatIndex:
    """One index per slot of a workspace, kept warm for the life of the process.

    The plain reading is reconciled first: it is idempotent and costs nothing when the
    files did not change, and it is what catches up a subject whose documents were
    uploaded before the reading existed.
    """
    raw_text.prepare_slot(ws, slot)
    entries = raw_text.chunks(ws, slot, study_config.RAG_CHUNK_CHARS)
    key = (ws.slug, slot)
    existing = _indices.get(key)
    if existing is None or existing.entries != entries:
        _indices[key] = FlatIndex(
            entries,
            cache_path=rag_index_path(ws, slot),
            label=_LABELS[slot],
            step_id=_STEP_IDS[slot],
        )
    return _indices[key]


def warm(ws) -> None:
    """Read and index both slots before anything is timed.

    Built inside the arm, this one-off cost would land in the RAG baseline's `elapsed_ms`
    and its step would be swallowed by the blind filter, so the evaluation job calls it
    before the blind section starts.
    """
    for slot in (CORPUS, EXEMPLARS):
        index_for(ws, slot).ensure()


def build_query(commission: Commission) -> str:
    """Everything this arm has to search with: the topic and the free instruction.

    No `EMBEDDING_QUERY_PREFIX` — that prefix talks about curriculum concepts and was
    measured as an optimisation of the system, so it belongs to the system.
    """
    parts = [", ".join(commission.concepts)]
    if commission.instructions.strip():
        parts.append(commission.instructions.strip())
    return "\n".join(parts)


def retrieve(ws, slot: str, query: str, k: int) -> list[tuple[str, str, float]]:
    """Return the top-k pieces of one slot as `(key, text, score)`."""
    index = index_for(ws, slot)
    return [(key, index.entries[key], score) for key, score in index.search(query, k)]


def render_pieces(pieces: list[tuple[str, str, float]]) -> str:
    """Lay the retrieved pieces out verbatim, each under the document and position it came from."""
    blocks = []
    for key, text, _score in pieces:
        name, _, position = key.rpartition("#")
        blocks.append(f"--- «{name}», fragmento {position}\n{text}")
    return "\n".join(blocks)


def run(commission: Commission, context) -> ArmResult:
    """Retrieve pieces of the notes and of the exercises by plain cosine and generate one item."""
    item_type = context.exemplars_profile.item_type(commission.item_type)
    ws = context.workspace
    started = time.perf_counter()

    query = build_query(commission)
    theory = retrieve(ws, CORPUS, query, study_config.RAG_TOP_K_THEORY)
    exercises = retrieve(ws, EXEMPLARS, query, study_config.RAG_TOP_K_EXERCISES)
    retrieved = theory + exercises
    logger.info(
        f"RAG plano: {len(theory)} fragmento(s) de apuntes y {len(exercises)} de ejercicios "
        "por coseno — " + ", ".join(f"{key} ({score:.3f})" for key, _text, score in retrieved)
    )

    prompt = study_prompts.of(context.language).rag_generation_prompt(
        naive_prompt=build_naive_prompt(commission, context),
        theory_block=render_pieces(theory),
        exercises_block=render_pieces(exercises),
        schema=item_type.output_schema_str(),
    )

    resp = inference.generate_stream(
        model=commission.model or config.VARIANT_GENERATION_LLM,
        prompt=prompt,
        think=commission.effort,
        on_token=progress.token_sink("eval"),
        temperature=config.TEMPERATURE_GENERATION,
    )
    raw = resp.response or (resp.thinking or "")

    item, error = parse_with_repair(
        raw,
        lambda text: parse_item(
            inference.split_thinking(text).response, commission.fixed, item_type
        ),
        repair_model=config.REPAIR_LLM,
        max_attempts=config.MAX_JSON_REPAIR_TRIES,
        shape="objeto",
        format=item_type.stripped_schema(),
        # The workspace's set, not this arm's: what is repaired is JSON, not the baseline.
        prompts=context.prompts,
    )

    return ArmResult(
        arm="rag",
        status=OK if item is not None else FAILED,
        item=item.model_dump(mode="json") if item is not None else None,
        raw_response=raw,
        prompt=prompt,
        model=commission.model or config.VARIANT_GENERATION_LLM,
        provider=inference.engine_name(),
        exemplar_ids=[key for key, _text, _score in retrieved],
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        error=None if item is not None else str(error),
    )
