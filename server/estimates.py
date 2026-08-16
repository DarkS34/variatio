"""How long a build will take, worked out from the raw documents it will read.

A build is the one thing this app does that takes hours, and until now the UI said
nothing about it: a bar that reads «12 %» after ten minutes does not answer «do I wait
or do I come back tomorrow?». Generation and evaluation are deliberately left out —
they are a handful of calls whose length depends on what the model decides to write,
so a number there would be noise dressed as information.

The estimate is a sum of per-unit costs, and every unit is one the builder really
iterates over: a page to convert, a chunk to extract from, a domain to judge. What
multiplies each of them is measured (see `RATES`), never guessed, and the same phase
keys the builders declare in their `BUILD_PHASES` come back in the breakdown, so the
estimate can be read next to the bar it explains.

Checked against every build this instance has on record, over the same corpus:

    knowledge graph   3 214 s estimated   vs   3 335 s recorded   (-4 %)
    exemplars bank      260 s estimated   vs     258 s recorded   (+1 %)
    exemplars profile   149 s estimated   vs      92 s recorded   (+62 %)

The profile gap is not an error and must not be "fixed": that recording predates the
builder scanning the WHOLE corpus instead of a sample, so it timed strictly less work
than today's code does. The other two are the comparison that matters.
"""

import math
from dataclasses import dataclass
from pathlib import Path

from variant_generator import config, stages
from variant_generator.builders import _source_docs

from . import raw_data, review, settings

# Seconds per unit on the deployment box (one A40, 46 GB) with the models `config.py`
# names. These are timings, not intuitions, and RE-MEASURING IS THE ONLY WAY TO CHANGE
# THEM: a model swap moves every one at once and not by a constant. Measured — when the
# two top tiers briefly both pointed at `qwen3.8:27b-q8_0` (2026-08-15 to 08-16), the
# same calls cost 2.4x (extract), 3.2x (drop) and 8.7x (taggability) what they cost here,
# because with a reasoning model what dominates is how long it deliberates, not the
# prompt: one `link` call spent 948 s emitting 51 466 characters of thinking.
#
# Where a figure comes from, because the two sources are not equally strong:
#
#  - Most of the KG rates are the per-call averages of the one fully recorded build
#    (`instance/.runs/1a8c987b7698.jsonl`), which ran these models: 28 extractions,
#    10 merges, 8 drops, 7 links, 6 taggability calls. An average over a whole build
#    beats a single sample, and it is also what the backtest of this module checks.
#  - The rest is measured directly, one call each, for what that run does not isolate.
#  - `kg_domains_call` and `kg_link_call` were ALSO measured directly and came out 1.7x
#    and 2.2x higher (287 s and 261 s). That gap is an artefact of the probe, not news
#    about the models: a prompt rebuilt from the FINISHED graph carries the 170 relations
#    linking itself added, so the model is handed more evidence — and writes more — than
#    it ever sees at that point of a real build. The recorded figures win for that reason.
#  - `eb_extract_chunk` is the recorded bank build (`.runs/81cd7c3fb7e8.jsonl`): 9 batches
#    in 249.7 s. Measured directly it came out at 7 s, which is the same probe artefact
#    once more — those batches answered with 2 and 2 745 characters where the real ones
#    answer with 9 to 29 extracted items.
#  - `transcribe_page` is the 20 s/page recorded in `config.EXEMPLARS_TRANSCRIBE_MODEL`'s
#    own comment, NOT the 2.4 s measured here: those probe pages were the title slides of
#    a lecture deck and came back nearly empty, so they time an empty page, not a page of
#    exercises.
#
# The thread through all three corrections: what these calls cost is dominated by HOW MUCH
# THE MODEL WRITES, so any probe that feeds an atypical input times an atypical call. A
# real recorded build is the better instrument wherever one exists.
#  - Docling is CPU work and does not move with the model tier: 474 pages in 362 s in the
#    recorded build, and 0.3-0.6 s for a whole `.docx`.
RATES: dict[str, float] = {
    "docling_page": 0.8,
    "docling_document": 1.0,
    "transcribe_page": 20.0,
    "kg_extract_chunk": 9.2,
    "kg_embed_100_names": 7.0,
    "kg_merge_call": 59.0,
    "kg_drop_call": 51.0,
    "kg_domains_call": 170.0,
    "kg_leftovers_call": 5.0,
    "kg_link_call": 120.0,
    "kg_taggable_call": 109.0,
    "eb_extract_chunk": 28.0,
    "ep_scan_chunk": 5.0,
    "ep_consolidate_call": 96.0,
}

# What the corpus turns into, from the same recorded build: 251 723 characters became 28
# chunks and 353-399 concepts in 6-7 domains. The call counts every phase then makes are
# not guesses either — they are what `KnowledgeGraphBuilder` computes from those numbers
# with the batch sizes in `config.py`, which is why they are read from there below.
CHARS_PER_CHUNK = 9_000
CONCEPTS_PER_CHUNK = 14
CONCEPTS_PER_DOMAIN = 60
MERGE_GROUPS_PER_CONCEPT = 0.25
LEFTOVER_ROUNDS = 2

# Only used for a document that has never been converted, where there is no markdown to
# measure and the file size is all there is. A slide deck holds far less text than its
# bytes suggest and a .docx is compressed, hence two very different factors.
CHARS_PER_PDF_PAGE = 600
CHARS_PER_DOCX_BYTE = 0.12
PAGES_PER_PDF_MB = 60


@dataclass
class Load:
    """What one raw slot will make a builder read, and how much of it is already done."""

    documents: int = 0
    pages: int = 0
    chars: int = 0
    # Conversion is cached per document, so a rebuild usually pays nothing for it. These
    # are what is left to convert, and they are the difference between minutes and hours
    # when the slot holds PDFs that need transcribing.
    pending_pages: int = 0
    pending_documents: int = 0

    @property
    def chunks(self) -> int:
        return max(1, math.ceil(self.chars / CHARS_PER_CHUNK)) if self.chars else 0


# The panel asks for this on every visit and a document's page count only changes when
# the document does, so it is remembered per (path, mtime, size) rather than reopening
# every PDF of the corpus each time.
_PAGE_COUNTS: dict[tuple[str, float, int], int] = {}


def _pdf_pages(path: Path) -> int:
    stat = path.stat()
    key = (str(path), stat.st_mtime, stat.st_size)
    if key not in _PAGE_COUNTS:
        _PAGE_COUNTS[key] = _count_pages(path, stat.st_size)
    return _PAGE_COUNTS[key]


def _count_pages(path: Path, size: int) -> int:
    fallback = max(1, round(size / (1024 * 1024) * PAGES_PER_PDF_MB))
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return fallback
    try:
        return len(pdfium.PdfDocument(str(path)))
    except Exception:  # noqa: BLE001 - a broken PDF must not break the panel
        return fallback


# Bytes, not characters — the markdown is UTF-8 Spanish prose, where the two differ by
# about 2 %, and reading a whole corpus off disk to be right about that would cost more
# than the error does.
def _cached_chars(paths: list[Path]) -> int:
    return sum(path.stat().st_size for path in paths if path.is_file())


def _sources(kind: str) -> list[Path]:
    # `raw_base_data/` is the user's own data and nothing in the pipeline creates it, so on
    # a fresh install the directory is simply not there. That is "no documents", not an
    # error the panel should show instead of the chain.
    directory = raw_data.directory(kind)
    return _source_docs.list_source_files(directory) if directory.is_dir() else []


def _corpus_load() -> Load:
    """The corpus, which the KG builder reads through Docling and caches as one markdown."""
    ws = settings.workspace()
    load = Load()
    for path in _sources(raw_data.CORPUS):
        is_pdf = path.suffix.lower() == ".pdf"
        pages = _pdf_pages(path) if is_pdf else 1
        cached = _source_docs.markdown_cached(path, ws.markdown_cache_dir)

        load.documents += 1
        load.pages += pages
        if cached:
            load.chars += _cached_chars([_source_docs.markdown_cache_path(path, ws.markdown_cache_dir)])
        else:
            load.chars += _estimated_chars(path, pages, is_pdf)
            load.pending_pages += pages if is_pdf else 0
            load.pending_documents += 0 if is_pdf else 1
    return load


def _exemplars_load() -> Load:
    """The exemplars, which both builders read page by page — a PDF page is a model call."""
    ws = settings.workspace()
    load = Load()
    for path in _sources(raw_data.EXEMPLARS):
        is_pdf = path.suffix.lower() == ".pdf"
        transcribed = _source_docs.pages_cached(path, cache_dir=ws.markdown_cache_dir)
        pages = transcribed or (_pdf_pages(path) if is_pdf else 1)

        load.documents += 1
        load.pages += pages
        if transcribed:
            directory = _source_docs.document_cache_dir(path, ws.markdown_cache_dir)
            load.chars += _cached_chars(sorted(directory.glob("[0-9][0-9][0-9].md")))
        else:
            load.chars += _estimated_chars(path, pages, is_pdf)
            load.pending_pages += pages if is_pdf else 0
            load.pending_documents += 0 if is_pdf else 1
    return load


def _estimated_chars(path: Path, pages: int, is_pdf: bool) -> int:
    if is_pdf:
        return pages * CHARS_PER_PDF_PAGE
    if path.suffix.lower() in _source_docs.PLAIN_TEXT_EXTS:
        return path.stat().st_size
    return round(path.stat().st_size * CHARS_PER_DOCX_BYTE)


# PER-ARTIFACT MODELS ---------------------------------------------------------------------
#
# One function per artifact, returning `{phase key: seconds}` over the keys that builder
# declares. A phase that costs nothing (typing the relations is arithmetic) is still
# named, so the breakdown and the bar's segments always line up.


def _knowledge_graph(load: Load) -> dict[str, float]:
    chunks = load.chunks
    concepts = chunks * CONCEPTS_PER_CHUNK
    domains = min(12, max(3, round(concepts / CONCEPTS_PER_DOMAIN)))

    merge_calls = math.ceil(
        concepts * MERGE_GROUPS_PER_CONCEPT / config.KG_BUILDER_MERGE_GROUPS_PER_CALL
    )
    drop_calls = math.ceil(concepts / config.KG_BUILDER_CLEAN_BATCH_SIZE)

    return {
        "convert": load.pending_pages * RATES["docling_page"]
        + load.pending_documents * RATES["docling_document"],
        "extract": chunks * RATES["kg_extract_chunk"],
        "clean": concepts / 100 * RATES["kg_embed_100_names"]
        + merge_calls * RATES["kg_merge_call"]
        + drop_calls * RATES["kg_drop_call"],
        "domains": RATES["kg_domains_call"] + LEFTOVER_ROUNDS * RATES["kg_leftovers_call"],
        # One call per domain plus the one that crosses them. The crossing call reads the
        # whole inventory instead of one domain, but it measured cheaper than a domain
        # call (187 s against 261 s), not dearer, so it is not worth a rate of its own.
        "link": (domains + 1) * RATES["kg_link_call"],
        "curate": 0.0,
        "taggable": domains * RATES["kg_taggable_call"],
    }


def _exemplars_bank(load: Load) -> dict[str, float]:
    return {
        "convert": load.pending_pages * RATES["transcribe_page"]
        + load.pending_documents * RATES["docling_document"],
        "extract": load.chunks * RATES["eb_extract_chunk"],
    }


def _exemplars_profile(load: Load) -> dict[str, float]:
    return {
        "convert": load.pending_pages * RATES["transcribe_page"]
        + load.pending_documents * RATES["docling_document"],
        "scan": load.chunks * RATES["ep_scan_chunk"],
        "consolidate": RATES["ep_consolidate_call"],
    }


_MODELS = {
    review.KNOWLEDGE_GRAPH: (_knowledge_graph, raw_data.CORPUS),
    review.EXEMPLARS_PROFILE: (_exemplars_profile, raw_data.EXEMPLARS),
    review.EXEMPLARS_BANK: (_exemplars_bank, raw_data.EXEMPLARS),
}


def artifact(name: str, load: Load) -> dict:
    model, _ = _MODELS[name]
    # An empty slot has nothing to build, and the fixed cost of the phases that do not
    # depend on the corpus would otherwise quote a wait for a build that cannot start.
    # Zero is the honest answer here, and the one the UI reads as "no estimate".
    seconds = model(load) if load.documents else {}
    phases = [
        {"key": key, "label": label, "weight": weight, "seconds": round(seconds.get(key, 0.0))}
        for key, label, weight in stages.build_phases(name)
    ]
    return {
        "artifact": name,
        "seconds": round(sum(p["seconds"] for p in phases)),
        "phases": phases,
        "basis": {
            "documents": load.documents,
            "pages": load.pages,
            "chunks": load.chunks,
            "pending_pages": load.pending_pages,
            "pending_documents": load.pending_documents,
        },
    }


def snapshot() -> dict:
    """Every build's estimate, from whatever is in the raw slots right now."""
    loads = {raw_data.CORPUS: _corpus_load(), raw_data.EXEMPLARS: _exemplars_load()}
    return {
        "artifacts": {
            name: artifact(name, loads[slot]) for name, (_, slot) in _MODELS.items()
        }
    }
