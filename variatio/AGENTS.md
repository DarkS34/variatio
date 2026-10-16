# AGENTS.md — `variatio/` — the library

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Rules for the library: its engines, layout, settings, artifacts, builders, runtime, prompts and
wording. The transcription's rules are in `documents/AGENTS.md`.

## Runtime prerequisites

- `import variatio` is side-effect-free; `variatio/__init__.py` holds only logging setup and
  **must never reach `core.inference`** (it costs ~220 ms per import). Entry points that talk
  to models call `core.inference.require_engine()` (today `cli.main()` and
  `build_worker.main()`); stages never do.
- Engines: `ollama` (default) and `cerebras+ollama` ([core/cerebras.py](variatio/core/cerebras.py)).
  Every model Cerebras' catalogue lists (or `CEREBRAS_MODELS`, the fallback) is routed
  remotely; the guardrail and the embedder always stay on Ollama. `known_models()` never
  raises and remembers its last read.
- Cerebras strict mode: `cerebras.strict_schema` adapts every grammar (drops refused
  keywords and `title`, rewrites `const` as a one-item `enum`, closes objects that do not
  declare `additionalProperties`), wraps a root array as `{"items": …}` and unwraps the reply,
  and drops `strict` above 5 000 chars or on open-ended maps. Each degradation is warned once
  per schema per process. Images travel before text in the body.
- **The Cerebras rate limit is enforced before the call** from a flock'ed file ledger
  ([core/cerebras_budget.py](variatio/core/cerebras_budget.py)). **The ledger is the
  account's, not the tree's**: Cerebras limits the organisation, not the key, so it lives at
  `paths.cerebras_budget_path()` — `~/.local/state/variatio/cerebras_budget.json`
  (`$XDG_STATE_HOME` honoured), shared by every installation of this user — and
  `CEREBRAS_BUDGET_PATH` is only for an installation whose key belongs to another account.
  Per-model buckets, rolling minute and day windows, `usage` charges tokens, and **a header may
  only lower what is believed left — never raise the configured `CEREBRAS_MAX_*` ceilings**
  (reading `limit-*`/`remaining-*` as the account's budget once disabled the throttle).
  `wait` books a `Claim` before the call; `record`/`release` settle it; stale claims age out.
  Waits up to `CEREBRAS_MAX_WAIT_SECONDS`, refuses beyond it, refuses outright a call larger
  than a whole window.
- `config.json` holds one settings profile per engine (`profiles.<engine>`); switching engine
  swaps the whole model set and switching back recovers it.
- Ollama at `OLLAMA_HOST` (`localhost:13434`, a forwarded port to a remote A40). Read VRAM
  through `/api/ps`, never `nvidia-smi` (that is this machine's card). `OLLAMA_MAX_LOADED_MODELS ≥ 3`.
- The API unloads models after 30 min idle (`server/jobs/idle.py`), reading only the job
  queue — which is why every model call of the process must go through a job.
- **Nothing is warmed.** `inference.ensure_models()` checks, pulls or raises; it sends no
  warm-up call. The required set comes from the registry (`GUARDRAIL_LLM`, `EMBEDDING_LLM`,
  `settings.derived.PHASES`, every offered generation model).

## `variatio/` layout

The root holds three files only: `config.py`, `cli.py`, `__init__.py`. Everything else is one
of three kinds:

- **Vocabulary** (consulted, never doing work): `core/`, `settings/`, `loaders/`, `prompts/`, `wording/`.
- **Work**: `builders/` (raw → artifacts, authoring) and `runtime/` (artifacts → exercises:
  `generator.py`, `tagger.py`, `taggability.py`, `checks.py`, `embedder/`, `screening/`).
- **The door**: `entrypoints/`.

Two rules (rewritten 2026-10-16: the earlier wording, «only `entrypoints/` takes a
`Workspace`» and «only `builders/` and `runtime/` call the model», was never true):
**`entrypoints/` is the library's public door; `builders/` and `loaders/` take a `Workspace`
only to resolve their own paths, and `runtime/`, `prompts/`, `wording/` and `settings/` do
not import it**; and **inside `variatio/`, only `cli.py`, `builders/`, `runtime/`,
`documents/` and `core/` import `core.inference`** (D-230) — `documents/pages/` transcribes
with the vision model, and `core/repair.py` and `core/vectors.py` call it on behalf of
`builders/` and `runtime/`. `runtime/__init__.py` and `core/__init__.py`
are empty/docstring-only on purpose (numpy cost; an import cycle). A module that outgrows one
job becomes a package named after itself whose `__init__` re-exports the public names. Do not
put a component back at the root.

- `core/`: `inference` (engine boundary: all model traffic via `generate()`/`embed()`/
  `embed_batch()`; never call an SDK from business logic), `ollama` (the local engine, the one
  importer of the `ollama` SDK; `inference` reaches it lazily), `cerebras`, `cerebras_budget`,
  `progress`, `json_io`, `paths`, `dotenv`, `workspace`, `lexicon`, `repair`
  (`parse_with_repair`, requires an explicit `shape`), `repetition`, `vectors` (L2
  normalisation, batched embedding, the query/document prefixes; shared by the builders,
  the embedder and the tutor).
- `loaders/`: `knowledge_graph`, `exemplars_profile`, `content_context`, `relations`, `locale`
  (the package was `instance/` until 2026-10-08, the directory's old name).
  The bank has no loader module; `entrypoints/initialize.py` reads it inline.
- Import `config` from the root and read `config.X` by module attribute; **never
  `from ..config import X`** — the hot rewrite depends on it.

## `Workspace` — every per-instance path, as data

[workspace.py](variatio/core/workspace.py) is a frozen dataclass over `root` deriving every
path (`artifacts/`, `cache/`, `raw/`, `generations/`, artifacts, derivations, host state). It imports nothing
from the package. Root paths live in [paths.py](variatio/core/paths.py). **There is no
default workspace**: `ws` is required everywhere, `paths.workspace("")` raises, an
installation may hold zero workspaces and an account may belong to none. A component with a
path parameter requires it. No cache key is a path, so a workspace is portable.
`server/core/installation.py` has `workspace_for(slug)`, never a no-argument `workspace()`.
**The artifacts' directory is `artifacts/`** (2026-10-08; it was `instance/`, a word that also
named the loaders' package and the whole subject). `paths.workspace`, the one door every
workspace is opened through, renames an old tree's `instance/` the first time it opens it
(`adopt_legacy_layout`: an atomic rename, a lost race harmless, and nothing touched when both
names exist). A tree renamed so is no longer readable by a version from before the rename.
`/api/health` says `paths.artifacts` and the disk usage `artifacts`, where both said `instance`.

## Settings (`variatio/settings/`)

- `config.py` is an **index of bare annotations** plus `apply(globals())`; values live in the
  registry (`settings/registry/*.py`), each `Setting` carrying its measured `doc`, `Impact`
  (`NONE ENGINE CONTEXTS REINDEX LOCKED` — what a change invalidates), bounds and flags.
- **Every setting names the stages that read it** (`stages`, the owner first; `types.STAGES`
  is the pipeline's, the registry appends the study's) and the model call it is drawn under
  (`phase`, a `PIPELINE` phase of its owner's lane). Engine, tunnel and logging have none.
  `tests/settings/test_setting_stages.py` pins it; the panel has one screen per stage (an
  optional function's in that function's own admin tab). `types.STAGES` is
  `transcription, graph, bank, generation` since 2026-10-08: the profile's calls and the
  taggability review are the bank's lane, in the order they run before the extraction.
  The study's own settings say `("evaluation",)`; which PIPELINE settings a session also
  reads is `consumers/evaluation/settings.READS`, never a stamp inside `variatio/`.
- Precedence: default < `config.json` < environment. An invalid value warns and falls back.
  **`config.json` stores every non-secret value and beats the registry**, so bumping a
  registry default alone changes nothing on an installation — edit `config.json` too.
- `derived.py` computes phase models, `VARIANT_GENERATION_LLM` (first of `generation.models`),
  `LLM_CONTEXT`, prerequisite relation, etc. Secrets (`secret=True`, `editable=False`) never
  enter `config.json` nor leave the API.
- A renamed setting answers to its old name in **one** place: `store.LEGACY_KEYS`.
- Map-valued settings are leaves (`store.map_keys`), not namespaces.
- **There is no main model**: each of the phase settings names its own model. Per-phase
  reasoning is a switch (`reasoning.phases.*`) plus an effort (`reasoning.effort.*`,
  default `low`); `derived` resolves `THINK_<PHASE>` to `False` or the level string.
  Switching a grammar phase's reasoning on drops its grammar. `inference._think_option` and
  `cerebras.reasoning_effort` are the only places that turn `True` into a level
  (`reasoning.default_effort`, default `low`).
- **Every model call samples with its own triple**, `sampling.phases.<phase>.{temperature,
  top_k,top_p}` (engine-scoped, declared from `PIPELINE` in `registry/sampling.py`), resolved
  by `inference.sampling(phase, think)` and passed as `sampling=` — never a bare temperature.
  Empty is inherited: a phase reading with another's model takes that phase's values
  (`derived`), the temperature then follows the judging pair by `think`
  (`TEMPERATURE_DETERMINISTIC`/`_REASONING`), top-k/top-p are not sent. Transcription, variant,
  repair and scenario keep a temperature of their own (`TRANSCRIBE_TEMPERATURE`,
  `TEMPERATURE_GENERATION`, `TEMPERATURE_REPAIR` are those keys' names). Cerebras drops a top-k
  with one warning per model.
- `LLM_CONTEXT` caps the KV cache per model (`context_window.overrides` 65536 for phases;
  guardrail 4096). Lowering one truncates silently — re-measure first.
- The evaluation's settings, its lane (`LANE`: scenario, local arms, external arm) and
  `READS` are declared in `consumers/evaluation/settings.py`, picked up by an optional import — the
  one place `variatio/` names the evaluation.
- The tutor's are declared the same way in `consumers/tutor/settings.py` (`LANE` «Tutor», stage
  `tutoring`, last; `READS`; `MODEL_KEYS`), picked up by an optional import that switches off
  only on `ModuleNotFoundError` for `consumers.tutor` itself. Their names are empty: they are read
  through `consumers/tutor/config.py`, never `variatio.config`. `registry.EXTRA_MODEL_KEYS` gives a model named
  only there the context cap (`derived`) and the deletion guard (`required_models`).

## Which model writes a variant

`generation.models` is the offered shortlist (engine-scoped, `min_items=1`);
`VARIANT_GENERATION_LLM` is its first entry and is what the CLI and the evaluation use. The
commission picks the model (checked twice: 422 at submit, `entrypoints.resolve_generation_model`
in the handler). Every offered model gets the context override and is protected by
`required_models()`. `generation.fixed_effort` + `generation.fixed_effort_levels` let the
installation lock and set a model's effort; `entrypoints.resolve_generation_effort` has the
last word; reasoning switched off is never turned on. `GET /api/health` carries
`models.offered`.

## The library

## Artifacts

Each artifact has a stem threaded through by role: `raw/raw_<stem>/` →
`variatio/builders/<stem>_builder` → `artifacts/<stem>.json` → loader.

- `knowledge_graph.json` — curated schema (`concepts_by_domains`,
  `generic_non_taggable_concepts`, `taggability_reviewed`, typed `relations`). The number and
  types of relations are variable; the loader stays relation-agnostic and cycle-checks
  `acyclic` relations. The builder only writes `knowledge_graph_autogenerated.json`; curation
  into the curated file is manual; `initialize` falls back to the draft with a warning.
- `exemplars_bank.json` — example items, plus the tagger's `concepts`/`primary_concept`.
  Each says where it comes from (`origin`, 2026-10-14): `extracted` from the documents
  (`C###`), `manual`, written by a teacher (`M###`), or `generated`, a generated exercise
  passed into the bank (`G###`); the last two with `added_by` (an account id) and `added_at`.
  An exercise without the field is read by its id (`bank_edit.origin_of`). `origin`,
  `added_by` and `added_at` are reserved field names of the profile.
- `exemplars_profile.json` — the content schema (`fields`, `general_generation_rules`,
  `primary_field`, `embed_fields`); validated into a runtime Pydantic `ContentItem`. This is
  how a use case is instantiated. The profile builder is a draft generator and unstable.
- `content_context.json` (+ `_autogenerated` draft; curated wins) — the subject in prose plus
  three named facts (`subject`, `educational_level`, `language_of_instruction`). **It has no
  builder of its own**: the graph and profile builders each synthesise it in a final
  `context` phase. `prompt_block()` is the only renderer; capped at
  `CONTENT_CONTEXT_MAX_CHARS` (900); it feeds the description fingerprint. Read-only on
  screen (under «Mi perfil → Asignaturas y ejercicios»); `PUT /api/context` still exists.
- `artifacts/locale.json` — the workspace's prompt language, chosen at creation and never
  after (relation labels are baked into the graph).

## Builders (`variatio/builders/`)

`entrypoints/build.py` is the only importer. The document plumbing they read through is
`variatio/documents/` (`files`, `markdown`, `chunking`, `pages`, `office`; outside `builders/`
since 2026-10-16, D-228, as the transcription and the server read it too); only its `pages/`
package talks to a model.
Builders use `inference.generate()`, never `generate_stream()` (a build runs out of process).

**Knowledge graph** ([knowledge_graph_builder/](variatio/builders/knowledge_graph_builder/)):
extract → clean → curate, handing dicts in memory; only `curate()` writes.

- Relation vocabulary is `loaders/relations.py` per language. The `verbose` labels
  («tiene como prerrequisito», «se engloba en», «se relaciona con») are load-bearing: the
  loader indexes by them. `ORIGEN`/`DESTINO` (SOURCE/TARGET) slot names live in
  `CATALOG_WORDS` and in the prompts' prose. The hierarchy is ONE relation, `se_engloba_en`.
- Every concept is anchored to up to three corpus passages (`cache/concept_sources.json`,
  cut by paragraphs, navigation paragraphs dropped, only for concepts a chunk yielded). **No
  anchoring beats a false one** — never restore a «head of chunk» fallback.
- Domains: one call names the blocks (sees every concept, no evidence); `assign_round`
  places concepts in batches; `place_leftovers` retries. `KG_BUILDER_UNCLASSIFIED_DOMAIN` is a
  sentinel, never a domain name. The naming call runs without reasoning — with it the model
  returned empty answers.
- **The units are written in the order they are taught**, in two steps (user's request,
  2026-10-05). The documents are read in the order of their NAMES as a person reads them
  (`documents.name_order`: case and accents folded, a run of digits counted as its number —
  by bytes «Bloque 10» came before «Bloque 2»), which `/raw` lists them in too. Then the call
  that finds the units (`segment_syllabus_prompt`, and the naming call when the corpus has no
  heading index) is asked, between finding them and naming them, to ORDER them: the numbering
  of headings and document names leads, the logic of the subject follows, and in doubt the
  outline's order stays. `accept_units` keeps the answer's place as `order` and still returns
  the units by chunk, because a unit ends where the next one of the corpus opens;
  `curate_units` writes the grouping by `order`, and `taught_positions` moves each unit's
  chunks as a block so «earlier» still means «taught earlier» for the linking prompts and the
  cycle breaker. Measured on eight real outlines: a corpus whose files were «Copia de Tema 4…»
  and «Tema 1…» opened on arrays and now opens on its first topic; a corpus already in order
  kept it.
- `KG_BUILDER_MERGE_QUALIFIER_PATTERN` and the unclassified name fail silently if removed.
- Progress is a weighted phase plan (`BUILD_PHASES`); the client reads it over REST.
  `_StepHandle.start()` reports the in-flight unit as not done; `tick` means done.

**Exemplars bank**: batches markdown with one-block overlap, extracts with an LLM, dedups by
folded primary field, validates against `ContentItem`. **With a remotely served model it asks
WITHOUT a grammar** (`_grammar_costs_the_text`): Cerebras' constrained decoding mangled every
non-ASCII character into `\u00XX` garbage. The repair drops its grammar too. The prompts ask
for non-ASCII characters written as themselves.

**Profile**: `guarantee_difficulty` runs on every consolidation route.

## Difficulty

Every modality carries a difficulty field; **the ladder is shared, only the criterion is the
modality's own**. The artifact shape is an ordinary field (`schema.enum`, `description`,
`guidance.extraction`, `decided_by: "user"`). The field name is the prompt set's
(`nivel_dificultad` / `difficulty_level`); writers resolve it via `locale.difficulty(ws)`,
readers via `ItemType.difficulty_field`. Rank = position in the modality's own enum;
unranked sorts last. The criterion has a shape the client splits (`«rung»:` markers,
`web/src/lib/difficulty.ts`, needs ≥2 marks else shown whole) and writes back: the types of
exercise (step 3's first part) correct it one rung at a time, each in a box beside its name
under the sentence that says
what the scale measures (`DifficultyEdit`), and `joinCriterion` joins them into the ONE
string the artifact keeps, every rung opened as soon as one is written. `guarantee_difficulty` is a
floor, never a rewrite; it keeps the field out of `embed_fields` and writes it last. It is
not a row in «Campos de …»; the generate form asks «¿De qué nivel?» regardless of
`decided_by`, and admissibility owners include it regardless too.

A modality may also declare **one variant decision field** (e.g. diagram kind) when its
exemplars split along a discrete form of the deliverable.

## Fields a commission may leave out

A field marked `omittable: true` is one whoever commissions chooses to have or not (user's
request, 2026-10-05). The mark is set by hand in the types of exercise («Se elige al generar»); no builder
writes it, and absent means the field is always written. The validator refuses it on the
primary field and on the difficulty. A commission names what it leaves out (`omit`, a job
parameter and `--omit` on the CLI); `ItemType.without(names)` returns a second reading of
the same modality without those fields, and the generator reads that one everywhere: the
fields asked of the model, the few-shot block, the schema of the repair, the parse, the
checks and the admissibility owners. A name the profile does not mark is ignored with a
warning, never refused, so a commission saved under an earlier profile can be repeated; a
value pinned on a field left out is dropped the same way (`clean_fixed`). The field stays in
the profile and in the bank. The record keeps `commission.omit` as asked and
`resolved.omitted` as run. The evaluation never leaves a field out: a comparison is of
whole exercises (`toEvaluationParams` strips `omit`, and its form does not ask).

## Taggability

Not part of the builder: a job (`review_taggability`) judged per domain against the
profile's modalities and real bank samples; operative test is discrimination, tie-break
«exclude when in doubt». A build writes `taggability_reviewed: false`; the library states the
flag and does not enforce it. `entrypoints/taggability.review_taggability(ws)` assembles it and
returns data; the handler writes through `kg_edit.set_non_taggable`. Since 2026-10-08 it runs
at the head of every collection of the bank and nowhere else, skipped when its inputs did not
change (see *Build chain and approvals* in `server/AGENTS.md`); no screen names it but the collection's own rows.

## Entry points (`variatio/entrypoints/`)

Mechanism, not policy: return data, raise `MissingArtifactError`, never print, never exit,
never auto-trigger heavier phases, and never import the engine. `_artifacts.py`,
`transcribe.py`, `build.py` (profile before bank), `initialize.py` (loads artifacts, builds
embedder, tags only pending items when `tag=True` — tagging BEFORE enrichment is the warm
start; initialize once per process), `descriptions.py`, `taggability.py`, `generate.py`.

## Runtime components (`variatio/runtime/`)

Take objects, return data, know no `Workspace`, write no files.

- **Embedder**: concept index from LLM-written *descriptions* (never names), fused per
  concept as `α·description + (1-α)·centroid(exemplars)` (weighted, L2-normalised). Retrieval
  is `max(cos(q, merged[c]), max cos(q, e))` over exemplars whose **primary_concept** is c.
  Batched, memoised, float32, `.npz` caches keyed by fingerprint. Only
  `use_in_embedding: true` relations feed descriptions; `relacionado` stays on. Descriptions
  are written automatically at `initialize`, saved per concept; impersonal voice,
  `DESCRIPTION_SCHEMA`, `think=False`.
- **Tagger**: embedder candidate band → LLM verification with descriptions and inter-candidate
  relations; per-item escalation (think retry, then wider `TAGGER_FALLBACK_TOP_K`).
- **Generator** (`generator.py`: `VariantGenerator`, `GeneratedVariant`): few-shot from the
  bank, curriculum scaffolding, repair/validation. `assumed_known()` **intersects** the
  prerequisite closure with the curriculum; `forbidden()` **subtracts** it. Prerequisites are
  `descendants` in networkx (`A → B` = B is prerequisite of A); swapping either silently
  produces plausible wrong lists. **Without a curriculum, what comes after the target may be
  USED but not PRACTISED** (`checks.closure_rule`: `practises` — the tagger's primary must not
  lie after the target); with one, forbidden concepts may not be mentioned.
- **Checks** (`checks.py`): `CHECK_MAX_RETRIES` = 2; a flag names something to look at; the
  tagger flag reads `targets_found` (a target among the tags), not the primary.
- **Screening** (`runtime/screening/`): `guardrail` then `admissibility`, sequence in
  `screen_instructions` (one copy, used by the pipeline and the evaluation). Admissibility is
  a catalogue of four fixed slots (`ambito`, `elementos`, `extension`, `datos`) with owners
  derived per instance; answers are verified against those owners before belief; it **fails
  open** three ways. The ruling travels to the prompt as typed lines. A refusal raises
  `InstructionsBlocked` (a `ValueError` with `code = "instructions_blocked"`), copied onto
  `Job.error_code`; the client recognises it by code, never by sentence.

## Prompts and wording

- `prompts/es/` and `prompts/en/`, same modules and signatures (pinned by test), chosen per
  workspace. **JSON keys the model emits are never translated** (they are `schemas.py`'s
  grammar). The English set is unmeasured.
- Shared distinction across four prompts: **practicar ≠ usar** («could a student who masters
  everything except this concept still solve it?»).
- Didactic stance, not a teacher persona: solver is `el alumno`, requester is `quien pide el
  ejercicio`, never `el docente`; no classroom voice in items.
- `variatio/wording/` holds every code-composed string whose language must match the
  workspace (injection patterns, stopwords, labels, reasons, marks, prompt fragments);
  `beside(prompts)` resolves it. English attack vocabulary lives in `shared.py` for both sets.
  The settings registry and error messages are NOT in it (Spanish UI copy).

## Pipeline shape

`cli.main()` → `require_engine()` → (`build_missing()`) → `initialize()` → `generate()`.
Components never persist; every write goes through `json_io.write_json` (the only writer of
persisted JSON: mkdir, `ensure_ascii=False, indent=2`, atomic `.tmp` replace — approval hashes
are hashes of these bytes).

## Deliberate heuristics

Each looks like a bug and is intentional:

- `cleaning.norm_key` singularises the last word and the head of a noun phrase before
  `de`/`del`/`of`; never a middle word; keeps parentheses.
- `_break_cycles` removes DFS back edges of `acyclic` relations without choosing direction.
- `extract()` collects into sets; rarity is not evidence of noise.
- Each component owns its parser; `parse_with_repair` takes it as an argument.
- `_select_few_shot` applies `fixed` only when enough examples match; list-valued fields
  never reach the few-shot block.
- `stripped_schema()` deep-copies (Pydantic caches the schema).
- `EMBEDDER_SIMILARITY_THRESHOLD` (0.40) gates only the top-1; candidates are a fixed top-k;
  there is no relative margin. Err low when revisiting.
- Empty document prefix, non-empty query prefix: qwen3-embedding's prescribed usage.
- `_posteriors()` subtracts the curriculum while `_prerequisites()` intersects it.
- Bank batches overlap by one block and dedupe by folded primary field; ids are claimed after
  the duplicate check.
- `TRANSCRIBE_SEAM_CHARS` is not in the page fingerprint.
- `lexicon.mentions` matches a concept name holding a negation (`wording.NEGATIONS`: «no»,
  «sin», «ni»; «no», «not», «non», «without») literally only: the short negation drops out of
  the needles, and «Recursividad no final» read as mentioned by every text on «recursividad
  final», which failed every tutor reply on it as introducing a later concept.
- `pending_ids()` treats an empty `concepts` list as untagged, so rejections are retried.

## Closed decisions

One line per rule in force; the date, commit and reason of each are in
the root `DECISIONS.md`. Do not reverse one without the user's explicit request.

**Structure**
- D-013, D-014 — Settings in the registry + `config.json`; one writer (`store.write_file` →
  `json_io`); the dotenv loader lives in `core/dotenv.py`.
- D-016 — Knowledge-graph extraction lives in this repo; no `kg-builder`; the web app is the
  only graph viewer.
- D-024 — Content context is its own artifact, written by the other two builders; three named
  facts and one renderer.
- D-033 — Strings whose language must match the workspace live in `wording/`.
- D-034, D-035 — Screening is one package with two calls in fixed order (guardrail first); the
  sequence exists once.
- D-228 — The document plumbing (files, markdown, chunking, page transcription, Office) is
  `documents/`, not a part of `builders/`.

**Prompts and the graph**
- D-036 — Two prompt sets per workspace; JSON keys never translated; sets interchangeable.
- D-037 — UI language is the account's, prompt language the workspace's,
  `language_of_instruction` the corpus's: three axes.
- D-038, D-039 — Every modality carries a difficulty; shared ladder, local criterion; the
  criterion's `«rung»:` shape is legislated by the prompt.
- D-040 — `guidance.generation` is hand-written only; modality rules carry generation.
- D-041, D-042 — Prerequisite lists are transitive closures bounded by the curriculum, with
  opposite set operations; without a curriculum, later concepts may be used, not practised.
- D-043 — The curriculum is the course's progress, set by its teachers in «Clase»: a
  suggestion the generate form offers in one press, never a bound.
- D-046 — Syllabus units are in teaching order: documents read in the natural order of their
  names, units ordered by the prompt; code never sorts them back.
- D-048, D-049, D-050 — One hierarchy relation (`se_engloba_en`); `relacionado` stays in
  embeddings; no wholesale regeneration of descriptions without benchmarking retrieval.
- D-051, D-052 — No anchoring beats a false one. Descriptions are impersonal and
  grammar-constrained.
- D-053 — The free-text field is a four-slot catalogue, judged after the guardrail, failing
  open, verified against derived owners.
- D-054, D-055, D-056 — Diagrams are transcribed as Mermaid; grammatical variants are one
  concept; a profile may declare one variant decision field per modality.

**Models and inference**
- D-057, D-058 — Open weights only; `cerebras+ollama` is the one hosted exception, per
  installation. No other hosted providers without asking. No fallback to Ollama when the
  Cerebras budget runs out.
- D-059 — Nothing is warmed; `ensure_models` only checks and pulls.
- D-060 — No main model; every phase names its own.
- D-061…D-064 — Judging/generating default `qwen3.8:27b-q8_0`, reasoning default `low`; `max`
  is `high` on that model; `qwen3.6:35b-a3b-q4_K_M` is broken — never re-add.
- D-065, D-066 — The domains naming call runs without reasoning; the phase context window is
  65536.
- D-067 — Embedding model fixed at `qwen3-embedding:4b`.
- D-068, D-069 — The Cerebras throttle is a hard cap no header may raise; the gate books claims.
- D-070 — The Cerebras ledger lives outside the tree, shared by default: the quota is the
  account's.
- D-072 — No grammar to a remote model on the bank extraction or its repair.
- D-073 — The commission chooses its writing model from the offered list; rows record it.
- D-074 — Every model call has its own temperature, top-k and top-p; empty inherits.
- D-086 — gpt-oss is not used; no code names it.
