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
# the single-user layout this repo always had, hanging off PROJECT_ROOT, which made the
# first instance a special case in every listing and put it somewhere no other instance
# could be. Moved into the tree on 2026-08-17 by explicit user request: one shape for every
# instance, and `workspaces/` as the only directory holding user data. The move is byte for
# byte — the `.npz` and the markdown cache are fingerprinted by content and not by path, so
# nothing was re-embedded.


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

# Cuánto puede estar el servidor sin ejecutar un solo trabajo antes de soltar la GPU
# (`inference.unload_all()`, que es `ollama stop` de cada modelo residente).
#
# `OLLAMA_KEEP_ALIVE=24h` es lo que mantiene los tres modelos calientes durante una sesión
# de trabajo, y eso es lo que se quiere mientras se está trabajando: los 29 GiB residentes
# no se pagan dos veces. Lo que no tiene sentido es que sigan ahí toda la noche porque
# alguien dejó la pestaña abierta, en una tarjeta que es de todos.
#
# 30 minutos porque es la escala de la pausa que NO es una pausa de trabajo: entre dos
# etapas de la cadena pasan minutos, no media hora, así que a este umbral no se llega
# revisando un grafo — se llega habiéndose ido. Recargar los tres modelos cuesta ~30 s, que
# es ruido al lado de cualquier construcción y de sobra tolerable en una generación suelta.
# 0 lo desactiva.
IDLE_UNLOAD_SECONDS = int(os.environ.get("VG_IDLE_UNLOAD_SECONDS", 1800))
IDLE_UNLOAD_POLL_SECONDS = 60

# ONE generative model, since 2026-08-17: the three tiers did not fit together on the A40
# (~45 GiB) and were evicting each other all day, and `gemma4:e4b-it-q8_0` (10.1 GiB) did not
# fit alongside a 30B-class one either, which made every JSON repair inside the extraction
# loop cost TWO ~10 s loads. That decision stands; only WHICH model changed.
#
# What stays resident is three models that DO fit at once — measured at 29.05 GiB of ~45 with
# the context sizes below — so nothing evicts anything: this one, the guardrail and the
# embedder. There is 16 GiB of headroom now, where the previous MoE left 3.5.
#
# The standing measurement against a 30B-class MoE was taggability: over the reference
# draft's largest domain (73 non-taggables) `gemma4:31b` returned 75 and `qwen3.6:35b-a3b`
# 66, i.e. the MoE under-excludes, the direction `review_taggable_concepts_prompt` legislates
# against. `qwen3.8:27b` is dense and reasons, so it is expected to do better here — but that
# is a PREDICTION, not a measurement, and it is the first thing to re-check on a real build.
#
# `qwen3.8:27b-q4_K_M` since 2026-08-18, replacing `qwen3.6:35b-a3b-q8_0` and reversing the
# 2026-08-16 revert, by explicit user request. What reopened the question is that Ollama can
# now cap how much a reasoning model deliberates: `think` takes an EFFORT LEVEL, not just a
# boolean, and `THINK_EFFORT` below pins every reasoning call to the cheapest one.
#
# The revert's reasons were real and are only PARTLY answered, so the numbers are here in
# full. All of them on the A40, on the same call — `link_domain_relations_prompt` over the
# reference draft's largest domain, 43 concepts, 5 441 characters, temperature 0:
#
#   qwen3.6:35b-a3b-q8_0  think=true    128 s   37 264 car. de razonamiento   92.0 tok/s
#   qwen3.8:27b-q4_K_M    think="low"   443 s   40 894                        29.1 tok/s
#   qwen3.8:27b-q8_0      think="low"   649 s   38 796                        19.0 tok/s
#   qwen3.8:27b-q8_0      think="high"  777 s   58 953        RESPUESTA VACÍA 19.2 tok/s
#
# Three things to read off that table before touching any of this:
#
# 1. THE EFFORT LEVEL DOES NOT REDUCE THE DELIBERATION MUCH. `low` still emits ~41 000
#    characters, i.e. about what the old MoE emitted with a plain `think=true`. What the
#    level moves is the CEILING (58 953 at `high`), not the floor. Anyone hoping to make
#    this model cheap by lowering the effort further will find there is nothing below `low`
#    except `think=False`, which turns reasoning off altogether.
# 2. THE COST IS THE DENSE DECODE, and it is the price of this decision: 29.1 tok/s against
#    the MoE's 92.0, so a curation call goes 128 s → 443 s and a build lengthens ~3.5x.
#    Accepted knowingly on 2026-08-18.
# 3. THE QUANTISATION IS NOT INTERCHANGEABLE HERE. The q4_K_M is 53 % faster than the q8_0
#    (29.1 vs 19.0 tok/s) and 16.5 GB against 27.9, and it obeys the effort level exactly
#    the same — measured, not assumed, in the token table under `THINK_EFFORT`. Unlike
#    `qwen3.6:35b-a3b-q4_K_M`, which is broken on this box above ~4 490 characters, this q4
#    answered the 5 441-character prompt with valid JSON. Do not "upgrade" it to the q8.
LLM_MAIN = "qwen3.8:27b-q4_K_M"
GUARDRAIL_LLM = "granite4.1-guardian:8b-q4_K_M"
EMBEDDING_LLM = "qwen3-embedding:4b"

# HOW HARD A REASONING CALL THINKS. `think` stays a BOOLEAN everywhere above this line —
# at the call sites, in the study's `Commission`, in the `generations.think` column and in
# the UI switch — and `inference` translates the `True` into this level at the very last
# hop. That split is the decision of 2026-08-18: the effort is a property of the engine, not
# a second axis for a call site or an evaluator to choose, and making it one would have
# meant a migration plus a study whose older sessions sat on a different scale.
#
# `low` and not something higher, measured on the A40 with `/api/generate`:
#
#     modelo                prompt_eval_count con think = true / low / medium / high
#     qwen3.8:27b-q4_K_M                          15 /  45 /  15 /  57
#     qwen3.8:27b-q8_0                            15 /  45 /  15 /  57
#     qwen3.6:35b-a3b-q8_0                        15 /  15 /  15 /  15
#
# Read it in three parts. `medium` IS the default — same token count as `true`, so it is not
# a rung, it is the absence of one. `high` costs 58 953 characters of deliberation on the
# real curation prompt and came back with an EMPTY response, which is the failure this
# model was reverted for in the first place. And the old MoE ignored the parameter outright:
# all four values produced a byte-identical answer, so the level is implemented per model by
# Ollama's renderer and CANNOT be assumed to exist — which is exactly why it is one constant
# here and not thirteen strings spread over the call sites.
#
# Ollama 0.32.13 accepts `high`, `medium`, `low`, `max`, `true`, `false` and 400s on anything
# else. `xhigh` does NOT exist. `max` is deliberately unused: it over-reasons.
THINK_EFFORT = "low"

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
# The fidelity comparison behind that (accents and a docstring's line break kept where
# gemma4:31b lost both, 20s against 31s a page) was measured on `qwen3.6:35b-a3b-q8_0`,
# which no longer holds this job — it followed `LLM_MAIN` into `qwen3.8:27b-q4_K_M` on
# 2026-08-18. The new model has the `vision` capability, checked, so the call works; whether
# it transcribes as faithfully is NOT measured yet. This is the cheapest thing in the
# pipeline to re-check (one page) and the most damaging to get wrong, since a corrupted
# transcription lands in the bank as an exercise whose answer has changed.
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
# The one phase whose call had to give up reasoning outright when `LLM_MAIN` became a
# reasoning model: asked to partition the whole inventory it answers inside the reasoning
# channel and returns nothing. The measurement and the reason are at the call site, in
# `knowledge_graph_builder/curation.py:curate_domains`. It is not the model that is wrong
# here, so this still points at `LLM_MAIN`; it is the thinking.
KG_DOMAINS_MODEL = LLM_MAIN
KG_DOMAINS_LEFTOVERS_MODEL = LLM_MAIN
KG_LINK_DOMAIN_MODEL = LLM_MAIN
KG_LINK_CROSS_DOMAIN_MODEL = LLM_MAIN
KG_TAGGABLE_MODEL = LLM_MAIN
KG_DIFFICULTY_MODEL = LLM_MAIN

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
# on the A40 through `/api/ps`, `LLM_MAIN` at 65536 + guardrail + embedder come to 29.05 GiB
# of ~45 (19.49 + 5.49 + 4.07). The guardrail's used to be 8192, which cost 1 GiB of KV cache
# and pushed the old total to 45.17 — just over, and the symptom was that screening one
# commission evicted the embedder. It only ever reads `GENERATION_INSTRUCTIONS_MAX_CHARS`
# (600 characters, ~200 tokens), so 4096 is still a tenfold margin.
#
# `LLM_MAIN`'s doubled from 32768 on 2026-08-18, with the move to a reasoning model. The rule
# changed underneath it: with `think` on, the window is no longer sized by the PROMPT but by
# prompt + deliberation, and the deliberation is the big half — the largest prompt in the
# pipeline is ~8 000 tokens while one `low` curation call spends ~13 000 on reasoning alone.
# The headroom freed by the lighter q4 is what pays for it, so it costs nothing to hold.
#
# What it does NOT fix, measured, is the empty answer on `curate_graph_domains_prompt`: over
# 203 concepts that call returns `response == ""` at 32768 AND at 65536, byte for byte the
# same (36 929 characters of reasoning, 11 611 tokens — about 13 200 in total, a fifth of the
# smaller window). The window was never the constraint there; see `KG_DOMAINS_MODEL`.
#
# Lowering this truncates silently, as always — and now it truncates the reasoning first, so
# the symptom is an empty or half-written answer rather than a missing tail of prompt.
LLM_CONTEXT = {
    LLM_MAIN: 65536,
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

# El anclaje de cada concepto al corpus: de qué párrafos del material de teoría salió.
# Es lo que permite enseñar que un concepto del grafo viene de algo real, y es lo que
# `concept_description_prompt` lee para no describir de memoria.
#
# Tres pasajes y no todos: un concepto troncal aparece en veinte fragmentos y los veinte
# dicen lo mismo; lo que aporta el tercero ya es repetición, y el fichero pasa de cientos
# de KB a unas decenas. 900 caracteres es un párrafo largo con su vecino — lo bastante
# para que se lea como material y no como un recorte.
KG_MAX_SOURCE_PASSAGES = 3
KG_SOURCE_PASSAGE_CHARS = 900
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

# Súbelo al cambiar `concept_description_prompt`, igual que `TRANSCRIBE_PROMPT_VERSION` con
# la transcripción de páginas. La huella de una descripción mira el grafo y el anclaje al
# corpus, que es lo que el prompt interpola — pero no el prompt, así que cambiar las reglas
# de redacción dejaba en caché descripciones escritas con las anteriores y no había forma
# de notarlo: el texto seguía ahí y el concepto seguía existiendo. La 2 es la que prohíbe
# la voz del alumno y exige la salida bajo gramática.
DESCRIPTION_PROMPT_VERSION = 2


# Per-concept difficulty ----------------------------------------------
# HOW MUCH EACH CONCEPT DEMANDS, in three tiers, blending two signals: what the model judges
# and what the structure of the graph says. It replaces a global, concept-blind difficulty
# criterion — the profile's says «básico si son una o dos operaciones aritméticas» for the
# whole subject — with one defined concept by concept, which is how competency-based
# assessment defines it: a threshold written per skill, not one scale shared by all of them.
#
# NONE OF THESE WEIGHTS IS MEASURED. They are the starting point, and there is free ground
# truth to calibrate them against: the bank items already carry a tier written by hand in the
# teaching material. `difficulty.bank_report(bank, data, field=...)` compares what is derived
# against what is written, and it is the first thing to look at before resting anything else
# on these numbers.
#
# Changing the number of tiers is NOT enough here: `concept_difficulty_prompt` names the three
# and describes them, and `generate_content_prompt` explains what each one asks for.
DIFFICULTY_LEVELS = 3

# The 50/50 the idea is named after, as a DEFAULT and not as a truth. Exact precedent:
# `EMBEDDER_DESCRIPTION_WEIGHT`, which also splits two signals measuring different things
# about the same object. 1.0 leaves the model's judgement alone; 0.0 the structure alone,
# which is the setting to measure with first, because it is the half that costs no GPU.
DIFFICULTY_LLM_WEIGHT = 0.5

# The structural half, and its internal split matters more than the 50/50 above.
#
# DEPTH RULES, not degree. A well-connected node of the graph is CENTRAL, not hard:
# `Variable` or `Función` have dozens of relations and are the first thing taught, while
# `Recursividad` has few and is hard. What does order a subject is how many concepts have to
# be mastered BEFORE, which is the depth in the prerequisite DAG — and it is exactly the
# stratification competency-based assessment does by hand when it splits the skills into
# foundational, core and advanced.
#
# The other three terms are corrections on top of that base, each with its own sign:
#   · NEEDS   = direct outgoing prerequisites — how much has to be brought in to start. Up.
#   · ENABLES = of how many concepts it is a prerequisite — backbone, taught early. DOWN.
#   · SPECIFICITY = being the specific side of «es un tipo de» / «es parte de» — a refinement
#     of something more general. Up, a little.
#
# The fallback relation («se relaciona con») enters NONE of them, and that exclusion is
# deliberate: it is the extractor's catch-all, so counting it measures how talkative the model
# was on that fragment of the corpus, not the subject matter.
DIFFICULTY_DEPTH_WEIGHT = 0.60
DIFFICULTY_NEEDS_WEIGHT = 0.25
DIFFICULTY_ENABLES_WEIGHT = 0.15
DIFFICULTY_SPECIFICITY_WEIGHT = 0.10

# The cuts of the final [0,1] into the three tiers. Thirds, because there is no measured
# reason to put them anywhere else yet.
DIFFICULTY_TIER_BOUNDARIES = (0.34, 0.67)


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
