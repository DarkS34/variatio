import os
from pathlib import Path

from .relations import BUILTIN_SCHEMAS
from .workspace import DEFAULT_SLUG, Workspace


# A real environment variable always wins: the file is the convenience, the export is
# the deliberate override. Only secrets and host settings live here — never a model
# name or a threshold, which belong in this file where they can be reviewed in git.
def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


# File Paths & Cache ----------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

_load_dotenv(PROJECT_ROOT / ".env")

# Every per-instance path lives on `Workspace`, never here: a path constant resolved at
# import time is exactly what makes two users overwrite each other's graph. What stays in
# this module is what is genuinely global — models, thresholds, the Ollama host.
WORKSPACES_DIR = Path(os.environ.get("WORKSPACES_DIR", PROJECT_ROOT / "workspaces"))

# `default` is a workspace like any other and lives where the others live. It used to be
# the single-user layout this repo always had — root PROJECT_ROOT, with `instance/`,
# `cache/` and `raw_data_1/` hanging off it — which made the first instance a special case
# in every listing and put it somewhere no other instance could be. Moved into the tree on
# 2026-08-17 by explicit user request: one shape for every instance, and `workspaces/` as
# the only directory holding user data. The move is byte for byte — the `.npz` and the
# markdown cache are fingerprinted by content and not by path, so nothing was re-embedded.


def default_workspace() -> Workspace:
    return workspace(DEFAULT_SLUG)


def workspace(slug: str | None = None) -> Workspace:
    slug = slug or DEFAULT_SLUG
    return Workspace(WORKSPACES_DIR / slug, slug=slug)


# Inference ----------------------------------------------
INFERENCE_ENGINE = "ollama"

_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "localhost:13434")
OLLAMA_HOST = (
    _OLLAMA_HOST if _OLLAMA_HOST.startswith(("http://", "https://")) else f"http://{_OLLAMA_HOST}"
)

# ONE generative model, since 2026-08-17. The three tiers did not fit together on the A40
# (~45 GiB) and were evicting each other all day: measured resident, this one takes
# 34.88 GiB and `gemma4:31b-it-q4_K_M` 19.49, so loading either dropped the other whole —
# and `gemma4:e4b-it-q8_0` (10.1 GiB) did not fit alongside this one either, which made
# every JSON repair inside the extraction loop cost TWO ~10 s loads.
#
# Consolidating is not about saving those 10 s. Timed on the A40 with one 7 448-character
# Spanish prompt: this MoE decodes at 99.6 tok/s against gemma4:31b's 25.2, and prefills at
# 1 709-2 277 tok/s against 1 060. The slow tier was the one owning the whole curation half
# of a build and the whole runtime (descriptions over every concept, tagging over every bank
# item), so what consolidating buys is that factor of four on those calls.
#
# What stays resident is three models that DO fit at once — 41.5 GiB of ~45, measured — so
# nothing evicts anything any more: this one, the guardrail and the embedder.
#
# The one measurement against it is taggability: over the reference draft's largest domain
# (73 non-taggables) gemma4:31b returned 75 and this one 66, i.e. it under-excludes a
# little, the direction `review_taggable_concepts_prompt` legislates against. If a re-run
# does not hold, the cheap way out is to give `KG_TAGGABLE_MODEL` alone back to
# gemma4:31b: one call per domain, one model switch per build, ~10 s.
#
# `qwen3.8:27b` in any quantisation must NOT come back: it is a reasoning model and the
# curation calls run with thinking on over the whole inventory — one
# `link_domain_relations_prompt` over 55 concepts spent 948 s emitting 51 466 characters of
# deliberation for 1 854 of answer, and `curate_graph_domains_prompt` spent 496 s to come
# back EMPTY. Quantising it makes each of those tokens cheaper, not fewer.
LLM_MAIN = "qwen3.6:35b-a3b-q8_0"
GUARDRAIL_LLM = "granite4.1-guardian:8b-q4_K_M"
EMBEDDING_LLM = "qwen3-embedding:4b"

# Raw exemplars transcription — shared by BOTH builders that read raw_exemplars_bank/,
# so there is one constant and not two that could drift and produce two different
# markdowns for the same file.
#
# What carries fidelity here is the PROMPT, not the model. Measured on Prog1_PEC1 p.1:
# without the character-by-character clause of `transcribe_page_prompt`, gemma4:31b
# rewrote `a -= 1` as `a = a - 1`, invented `8 - (n-i)` for `(n-i)`, and turned
# `x = x - 1` into `x = x + 1` — which inverts the answer to the very question being
# transcribed. With the clause, both 30B-class models come back faithful. Weakening that
# instruction silently reintroduces corrupt code into the bank.
#
# Between the two, the q8 kept the accent in «aquí» and the docstring's line break where
# gemma4 lost both, and it is faster (20s vs 31s a page), so it takes the job.
EXEMPLARS_TRANSCRIBE_MODEL = LLM_MAIN

# One constant per model call is still the unit of retuning, and that is the whole reason
# they survive a consolidation: pointing them all at `LLM_MAIN` is a decision, not a
# collapse, and any single phase can be moved off it without touching the other twelve.

# Exemplars profile builder
EP_SCAN_MODEL = LLM_MAIN
EP_CONSOLIDATE_MODEL = LLM_MAIN

# Exemplars bank builder
EB_EXTRACT_MODEL = LLM_MAIN

# Knowledge graph builder
KG_EXTRACT_MODEL = LLM_MAIN
KG_CLEAN_EMBEDDING_MODEL = EMBEDDING_LLM
KG_CLEAN_MERGE_MODEL = LLM_MAIN
KG_CLEAN_DROP_MODEL = LLM_MAIN
KG_DOMAINS_MODEL = LLM_MAIN
KG_DOMAINS_LEFTOVERS_MODEL = LLM_MAIN
KG_LINK_DOMAIN_MODEL = LLM_MAIN
KG_LINK_CROSS_DOMAIN_MODEL = LLM_MAIN
KG_TAGGABLE_MODEL = LLM_MAIN

# Runtime pipeline

DESCRIPTION_GENERATION_LLM = LLM_MAIN
CONCEPT_TAGGER_LLM = LLM_MAIN
CONTENT_GENERATION_LLM = LLM_MAIN


# Repair is the one call that fires from INSIDE a per-element loop, so it is also the one
# that must never be a model of its own: a separate small model does not fit next to
# `LLM_MAIN` on this box, and each repair would evict it and pay two ~10 s loads in the
# middle of a corpus. Whatever else moves off `LLM_MAIN`, this follows it.
REPAIR_LLM = LLM_MAIN

EMBEDDING_MODELS = (EMBEDDING_LLM, KG_CLEAN_EMBEDDING_MODEL)

# These are what make the three models co-resident, so they are not free to grow: measured
# on the A40, `LLM_MAIN` + guardrail + embedder come to 41.5 GiB of ~45. The guardrail's
# used to be 8192, which cost 1 GiB of KV cache and pushed the total to 45.17 — just over,
# and the symptom was that screening one commission evicted the embedder. It only ever
# reads `GENERATION_INSTRUCTIONS_MAX_CHARS` (600 characters, ~200 tokens), so 4096 is still
# a tenfold margin. Lowering `LLM_MAIN`'s truncates silently, as always.
LLM_CONTEXT = {
    LLM_MAIN: 32768,
    GUARDRAIL_LLM: 4096,
    EMBEDDING_LLM: 4096,
    KG_CLEAN_EMBEDDING_MODEL: 4096,
}


# Builders ----------------------------------------------
# Page-image transcription of raw exemplars. Docling reads these PDFs as text and loses
# three things at once: it detaches code blocks from the question that cites them, it
# collapses their line breaks, and it drops the colour that marks the correct option.
# Rendering the page and reading it as an image recovers all three.
TRANSCRIBE_DPI = 200
# Transcription is copying, not writing: at Ollama's default temperature the same page
# came back with `a = 99` and `if a < 0 : break` dedented out of their `while True:`,
# which silently changes what the exercise asks. Pinned to 0 for that reason.
TRANSCRIBE_TEMPERATURE = 0.0
TRANSCRIBE_MAX_RETRIES = 1
# Bump when transcribe_page_prompt changes: it is part of the page cache fingerprint.
TRANSCRIBE_PROMPT_VERSION = 1

# Only reached by the Docling fallback (non-PDF sources, or PDFs whose transcription
# failed): scanned pages whose text never made it into the PDF at all.
EXEMPLARS_OCR = True

EP_CHUNK_SIZE = 12_000
EP_SCAN_EXCERPT_CHARS = 400
EP_MAX_ITEM_TYPES = 6
EB_CHUNK_SIZE = 12_000

KG_BUILDER_CHUNK_SIZE = 12_000
KG_MAX_EVIDENCE_RELATIONS = 6
KG_BUILDER_PLURAL_SUFFIXES = ("s",)
KG_BUILDER_MERGE_QUALIFIER_PATTERN = r"\s+en (python|java)\b"
KG_BUILDER_UNCLASSIFIED_DOMAIN = "Sin clasificar"
KG_BUILDER_MAX_TITLES_PER_DOC = 3
KG_BUILDER_TITLE_UBIQUITY = 0.6

KG_RELATION_SCHEMA = "es"
RELATION_SCHEMA = BUILTIN_SCHEMAS[KG_RELATION_SCHEMA]
KG_PREREQUISITE_RELATION = RELATION_SCHEMA.prerequisite_verbose


# Embedding & Retrieval ----------------------------------------------
# It still says «el enunciado de un ejercicio» although `embed_fields` may now append the
# code the item hands the student. Generalising it to «un ejercicio» was tried and MEASURED
# WORSE, so the wording stays: on the reference bank it moved 17/152 top-1s and cost margin
# (0.0345 → 0.0328), dropping the lowest top-1 from 0.4065 to 0.3902 — under the threshold
# below, i.e. one item that got candidates stops getting any. On the multi-field test bank,
# where it should have paid off, it was a wash (top-1 0.6153 → 0.6045, margin +0.0014).
# Same lesson as embeddinggemma: a prefix is a measured claim, never an intuition.
EMBEDDING_QUERY_PREFIX = "Instruct: Dado el enunciado de un ejercicio, recupera la descripción del concepto del currículo que el ejercicio hace practicar al alumno, no la de los que solo usa como herramienta\nQuery: "

EMBEDDING_DOCUMENT_PREFIX = ""
EMBEDDING_BATCH_SIZE = 16

# Caps each field `embed_fields` appends AFTER the primary one, so one long code listing
# cannot crowd the others out of the context. Single-field profiles are not capped: their
# text stays byte-identical to the primary field, which is what keeps their cached vectors
# and the threshold below valid.
EMBEDDING_FIELD_MAX_CHARS = 2000
# The safe budget for one embedding call, enforced as a WARNING at initialize rather than
# by truncating. Measured on qwen3-embedding:4b at num_ctx 4096, and the two paths disagree:
# `embed_batch` (/api/embed) silently truncates above ~20 000 chars, while `embed`
# (/api/embeddings) raises a 500 at ~15 500 — so the same oversized item indexes fine and
# then blows up at tagging time. 12 000 keeps a margin under the lower of the two.
EMBEDDING_MAX_CHARS = 12_000

# Re-measured after `embed_fields` and it STAYS at 0.40 — the change does not move the
# distribution it gates. Cold (a fresh bank, scored against pure concept descriptions, which
# is the regime tagging runs in) the noise median went slightly DOWN, 0.3418 → 0.3329, and
# the lowest real top-1 barely moved, 0.5005 → 0.4938. Warm (the reference bank, scored
# against the merged index + the kNN leg, which is what the pipeline really does) the noise
# median is 0.3776 — that is the 0.382 recorded here — and the lowest top-1 is 0.6226.
# So 0.40 still sits above the noise in both regimes and below every observed real top-1.
EMBEDDER_SIMILARITY_THRESHOLD = 0.40
EMBEDDER_DESCRIPTION_WEIGHT = 0.5

DESCRIPTION_SIBLINGS_TOP_K = 8
DESCRIPTION_COLLISION_SIMILARITY = 0.85


# Tagging & Generation ----------------------------------------------
KG_BUILDER_MERGE_SIMILARITY = 0.80
KG_BUILDER_MAX_MERGE_GROUP = 8
KG_BUILDER_MERGE_GROUPS_PER_CALL = 10
KG_BUILDER_CLEAN_BATCH_SIZE = 60
KG_BUILDER_DOMAIN_BATCH_SIZE = 20
KG_BUILDER_DOMAIN_ROUNDS = 3

TAGGER_TOP_K_CANDIDATES = 10
TAGGER_FALLBACK_TOP_K = 30
MAX_FEW_SHOT_EXAMPLES = 4
MAX_JSON_REPAIR_TRIES = 3

GENERATION_INSTRUCTIONS_MAX_CHARS = 600
GUARDRAIL_CRITERIA = ("harm", "jailbreak")


# Evaluation ----------------------------------------------
# Only the Evaluation mode reads this block; the pipeline never imports `evaluation/`.
#
# The `*_MODEL_ID` names deliberately do NOT end in `_MODEL`: `inference.required_models()`
# collects those by introspection and `/api/health` demands them from Ollama, so the name
# would surface in the UI as a model that is never installed. Ending in `_LLM` would be
# worse — `prepare_models()` would try to pull it.
#
# `EVAL_EXTERNAL_PROVIDER` is a CHAIN in preference order, not a single name. The free tiers
# this arm runs on answer 429 halfway through a data-collection session, and a provider that
# stops answering hands over to the next one instead of costing the session its commercial
# proposal. Each provider brings its own key and its own model id, so the two can never be
# crossed — which is what the single `EVAL_EXTERNAL_API_KEY` made impossible. `none` (or an
# empty value) disables the arm.
#
# The keys come from the environment (or the gitignored `.env`) and default to empty: with
# no key at all the naive arm records itself `unavailable` and the session runs with two.
EVAL_EXTERNAL_PROVIDER = os.environ.get("EVAL_EXTERNAL_PROVIDER", "gemini,groq")


def _provider_chain(declared: str) -> list[str]:
    chain: list[str] = []
    for name in declared.split(","):
        name = name.strip().lower()
        if name and name != "none" and name not in chain:
            chain.append(name)
    return chain


EVAL_EXTERNAL_PROVIDERS = _provider_chain(EVAL_EXTERNAL_PROVIDER)


def _provider_settings() -> tuple[dict[str, str], dict[str, str]]:
    models = {
        "gemini": os.environ.get("EVAL_GEMINI_MODEL_ID", "gemini-3.6-flash"),
        "groq": os.environ.get("EVAL_GROQ_MODEL_ID", "llama-3.3-70b-versatile"),
    }
    keys = {
        "gemini": os.environ.get("EVAL_GEMINI_API_KEY", ""),
        "groq": os.environ.get("EVAL_GROQ_API_KEY", ""),
    }
    # An environment still exporting the old single-provider pair keeps working. The pair
    # moves TOGETHER onto whichever provider the chain leads with — the one that variable
    # used to select — because a key and a model id from different providers is precisely
    # the mix-up that would send Gemini's key to Groq's endpoint.
    legacy_key = os.environ.get("EVAL_EXTERNAL_API_KEY", "")
    first = EVAL_EXTERNAL_PROVIDERS[0] if EVAL_EXTERNAL_PROVIDERS else ""
    if legacy_key and first in keys and not keys[first]:
        keys[first] = legacy_key
        models[first] = os.environ.get("EVAL_EXTERNAL_MODEL_ID", "") or models[first]
    return models, keys


EVAL_PROVIDER_MODELS, EVAL_PROVIDER_KEYS = _provider_settings()

# Per attempt, so a chain of two waits for this twice in the worst case. The arm runs on a
# thread alongside the two local ones, which take minutes, so it is not the wall clock.
EVAL_EXTERNAL_TIMEOUT = 60.0

# Same k as the pipeline's few-shot, so the number of examples is not a loose variable
# between the arms: what the comparison isolates is the graph, not the prompt budget.
EVAL_RAG_TOP_K = MAX_FEW_SHOT_EXAMPLES


# Logging ----------------------------------------------
NOISY_LOGGERS = ("docling", "docling_core", "docling_ibm_models", "PIL")
NOISY_WARNING_MODULES = (r"docling.*", r"PIL.*")

# El detalle por elemento (un concepto, un ítem, un fragmento) se registra en DEBUG y
# queda fuera del registro: la barra de progreso ya lo dibuja, y un banco de 150 ítems
# o un grafo de 350 conceptos lo desbordarían. VG_LOG_LEVEL=DEBUG lo devuelve.
LOG_LEVEL = os.environ.get("VG_LOG_LEVEL", "INFO").upper()
