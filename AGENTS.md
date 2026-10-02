# AGENTS.md

Guidance for coding agents working in this repository.

**How to read this file.** It states how things work and what must not be undone. The
*Closed decisions* section is authoritative: if a request would reverse one, push back and
ask before implementing. Numbers quoted are measurements; re-measure before changing
what they justify. When a decision's reason is only summarised here, look for it in the
commit that introduced it (`git log -S`) before changing it.

## Project

*Knowledge Graph-Guided LLM Content Generator* — TFM (Máster en IA) for adaptive
educational content generation. It generates **learning items** (exercises, problems,
assessment tasks) grounded in a curriculum graph, from three inputs (knowledge graph +
exemplars bank + exemplars profile), over one pipeline serving student-facing exercise
generation and teacher-facing exam generation.

**The domain is education; the subject is a parameter.** Prompts reason about learning
objectives, prior knowledge and cognitive load, never about a particular subject — what is
taught comes from the workspace's `content_context` artifact + the KG. Generalising beyond
education is out of scope; hardcoding a subject is equally a regression.

## Branches

- **`variatio-web-eval`** (this tree, `/home/deploy/variatio`): the complete system WITH
  the study (`evaluation/`, `web/src/evaluation/`, the `evaluate` job, evaluator profiles,
  the stage questionnaires). Production serves a separate worktree, `/home/deploy/variatio-prod`.
- **`variatio-web`**: the product WITHOUT the evaluation. No worktree at present
  (`git worktree add ../variatio-noeval variatio-web` to recreate). Its route-order detector
  lives in `tests/server/test_route_order.py`.
- **`main`**: the library and its CLI alone.
- **The database never moves**: `evaluation_sessions`, `stage_evaluations` and
  `users.evaluator_profile` keep their migrations and ORM models on every branch.
- **Derived branches are brought forward by MERGING this one and re-removing what they do
  not carry** (never by cherry-picking). After the merge: `git rm` the study's files again;
  git's rename detection files new `tests/evaluation/` tests under `tests/server/` — delete
  them; the i18n catalogues conflict and the HEAD side is right; read `len(REGISTRY)` and
  `len(BY_NAME)` off the branch before writing `tests/settings/test_settings_registry.py`.
- `AGENTS.md` is tracked and travels with every branch; on `main` and `variatio-web` the
  evaluation sections describe code that branch does not carry.

## Commands

Dependency management is **`uv`** (`pyproject.toml` + `uv.lock` + `.python-version`).

- `uv sync` — install (package editable).
- `uv run variatio <transcribe|build|init|generate|all> --workspace SLUG` — the library CLI
  ([cli.py](variatio/cli.py)). `--workspace` is **required**; there is no default instance.
  `transcribe` reads raw documents into pages (`--slot corpus|exemplars|all`) and is never
  chained by anything; `build` creates missing artifacts; `init` loads, tags, warms indices;
  `generate` (`-n`, `--concepts`, `--item-type`, `--fixed FIELD=VALUE`, `--curriculum`,
  `--instructions`); `all` = build missing + init + generate.
- `uv run system [serve|import-instance|export-instance|export-generations|workspaces|create-workspace|db-check|create-user|users|grant|invite]`
  — API and admin ([server/cli/](server/cli/)). No subcommand means `serve`. `guarded()` wraps
  every command except `db-check` and `serve`. `PROG = "system"` matches `pyproject.toml`.
- `uv run pytest` — default `-m 'not corpus and not model'`. Suite split by subsystem under
  `tests/<subsystem>/`, each runnable alone; `conftest.py` and `fixtures/` at the root.
  - **Autouse fixtures exist because the suite runs inside the installation**: they redirect
    the Cerebras ledger, `DATABASE_URL` (throwaway SQLite), `paths.WORKSPACES_DIR` and
    `paths.LOGS_DIR` (session-scoped, because job threads outlive a test), stub Cerebras'
    catalogue, and point the invite-link key at a tmp path. Never let a test touch
    production state.
  - `chain_graph_path` is a three-hop prerequisite chain — the only shape where 1-hop and
    transitive differ.
- `uv run pytest -m corpus` — statistical checks of one real build's artefacts
  (`VARIATIO_MODEL_WORKSPACE`, default `default`; SKIPS when absent). They measure the
  artefact, not the code.
- `uv run pytest -m model` — the admissibility judge against a live Ollama (~17 calls).
- Web: `pnpm test` (vitest), `pnpm exec tsc --noEmit`, `pnpm build`, `pnpm check:color`,
  `pnpm check:ui`, `pnpm check:i18n`.

### Running locally

```bash
docker compose up -d postgres
uv run alembic upgrade head
uv run system import-instance --slug default
uv run system create-user --username tunombre --admin --workspace default
uv run system
```

Database commands fail with a plain message, not a stack. `serve` refuses to start when the
schema is behind or ahead of the migrations ([db/schema.py](server/db/schema.py)); `db-check`
reports it. Deploying a change with a migration or new dependency needs `uv sync` and
`uv run alembic upgrade head` before the restart. Migration 0015 drops the `generations`
table and refuses while a row has no file: on an installation that still has the table, run
`uv run system export-generations` (idempotent, `--dry-run`) before the upgrade.

### Dependencies

- `dependencies` — runtime pipeline only (httpx, loguru, networkx, numpy, ollama, tqdm,
  json-repair, pydantic). Every name there must be imported by the runtime.
- `[builders]` — Docling (~700 MB), python-pptx, pypdfium2. Imported **lazily**:
  `source_docs/files.LazyConverter` opens Docling only at `markdown.to_markdown`'s
  `convert()`, and `pypdfium2` only inside `source_docs/pages.py`. Never move those imports
  to module scope. Importing anything under `variatio/` must not import Docling or torch.
- `[server]` — FastAPI, uvicorn, SQLAlchemy/Alembic/psycopg, argon2-cffi, cryptography
  (`server/auth/links.py` only), pypdf (evaluation RAG reader).
- `[dependency-groups] dev` — builders + server.
- **LibreOffice is a system dependency of the builders** (`soffice`, looked up at call time)
  for rasterising EMF/WMF metafiles in Office files. Without it those pictures read as
  `[IMAGEN NO LEGIBLE]`.

### Runtime prerequisites

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
  (`/.cerebras_budget.json`, [core/cerebras_budget.py](variatio/core/cerebras_budget.py)):
  per-model buckets, rolling minute and day windows, `usage` charges tokens, and **a header may
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

## Architecture

The hard line: **`instance/` holds the instance definition (data), `variatio/` is the code
that produces and consumes it.** Top-level packages: `variatio/` (library), `server/` (API),
`evaluation/` (the TFM's study), `web/` (React client), `migrations/`.

### `variatio/` layout

The root holds three files only: `config.py`, `cli.py`, `__init__.py`. Everything else is one
of three kinds:

- **Vocabulary** (consulted, never doing work): `core/`, `settings/`, `instance/`, `prompts/`, `wording/`.
- **Work**: `builders/` (raw → artifacts, authoring) and `runtime/` (artifacts → exercises:
  `generator.py`, `tagger.py`, `taggability.py`, `checks.py`, `embedder/`, `screening/`).
- **The door**: `entrypoints/`.

Two rules, each one grep: **only `entrypoints/` takes a `Workspace`**, and **only
`builders/` and `runtime/` call the model**. `runtime/__init__.py` and `core/__init__.py`
are empty/docstring-only on purpose (numpy cost; an import cycle). A module that outgrows one
job becomes a package named after itself whose `__init__` re-exports the public names. Do not
put a component back at the root.

- `core/`: `inference` (engine boundary: all model traffic via `generate()`/`embed()`/
  `embed_batch()`; never call an SDK from business logic), `cerebras`, `cerebras_budget`,
  `progress`, `json_io`, `paths`, `dotenv`, `workspace`, `lexicon`, `repair`
  (`parse_with_repair`, requires an explicit `shape`), `repetition`.
- `instance/`: loaders — `knowledge_graph`, `exemplars_profile`, `content_context`, `relations`.
  The bank has no loader module; `entrypoints/initialize.py` reads it inline.
- Import `config` from the root and read `config.X` by module attribute; **never
  `from ..config import X`** — the hot rewrite depends on it.

### `Workspace` — every per-instance path, as data

[workspace.py](variatio/core/workspace.py) is a frozen dataclass over `root` deriving every
path (`instance/`, `cache/`, `raw/`, `generations/`, artifacts, derivations, host state). It imports nothing
from the package. Root paths live in [paths.py](variatio/core/paths.py). **There is no
default workspace**: `ws` is required everywhere, `paths.workspace("")` raises, an
installation may hold zero workspaces and an account may belong to none. A component with a
path parameter requires it. No cache key is a path, so a workspace is portable.
`server/installation.py` has `workspace_for(slug)`, never a no-argument `workspace()`.

### Settings (`variatio/settings/`)

- `config.py` is an **index of bare annotations** plus `apply(globals())`; values live in the
  registry (`settings/registry/*.py`), each `Setting` carrying its measured `doc`, `Impact`
  (`NONE ENGINE CONTEXTS REINDEX LOCKED` — what a change invalidates), bounds and flags.
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
  (`DEFAULT_THINK_EFFORT = "low"`).
- `LLM_CONTEXT` caps the KV cache per model (`context_window.overrides` 65536 for phases;
  guardrail 4096). Lowering one truncates silently — re-measure first.
- The evaluation's settings are declared in `evaluation/settings.py`, picked up by an optional
  import — the one place `variatio/` names the evaluation.

### Database (`server/db/`)

Postgres 16 + SQLAlchemy 2.0 + Alembic, all under the `server` extra; `import server` works
with no database. `Json = JSON().with_variant(JSONB(), "postgresql")`.

- **The ORM models describe what the migrations built**; `alembic` autogenerate against the
  live schema must report zero differences. Fix drift in the models, never with DDL.
- Artifacts are versioned rows keyed `(workspace, kind, stage, version)`; an unchanged hash
  reuses the existing row.
- **Reads come from files; writes are mirrored best-effort** (`server/db/mirror.py`) at three
  hooks: `storage.write_json`, `jobs/handlers._build`, `Approvals.approve/reopen`. A DB
  failure is one warning, never an exception. `.review_state.json` is the operational truth.
- `import_instance`/`export_instance` round-trip byte-identically; approval hashes are
  re-derived, never trusted.

### Identity (`server/auth/`)

Own passwords, own server-side sessions, no OAuth/IdP/JWT.

- **No registration endpoint, ever.** Accounts come from single-use invitations or
  `create-user`. The person registering chooses their username, language and evaluator profile.
- Argon2id; policy is length plus rejecting the obvious. No HIBP.
- **Username enumeration is refused in three places at once** (`/login` uniform answer +
  decoy hash timing, `/forgot` always 202). Weakening one re-opens it.
- Sessions: opaque token, SHA-256 in DB, sliding 14 d + absolute 30 d, rotate on login and
  password change, password change revokes other sessions.
- **Authorisation is a membership row, checked on every route** (`auth.VIEW`/`EDIT`/`MANAGE`).
  The admin bypass exists only in `auth.deps.access_for`. The WebSocket authenticates before
  `accept()` (close 4401) and filters events by workspace.
- CSRF is an origin check (`middleware.py`); CORS off by default. Rate limiting is in memory,
  keyed by IP and account.
- The username is the identity; `users.email` is an optional delivery detail, shown only when
  mail is configured (`mail_configured` on `/api/auth/me`). No «forgot password» link on the
  login screen; admins hand out reset links. No password generator anywhere.
- `users.evaluator_profile` (`teacher`/`student`/NULL) is **not an authorisation**.
- Invitations are the admin's alone (`routers/admin.py`): chosen expiry (floor, no ceiling),
  an internal alias never shown to the invitee, batches, link kept **sealed** with Fernet
  (key in `VARIATIO_INVITE_LINK_KEY` or `/.invite_link_key`, never in the DB), readable again
  via `GET /{id}/link`, and pastable back after deletion. The sealed copy dies with the use.
- Deleting an account: its generated exercises stay as files nobody reads any more;
  `evaluation_sessions` keep their rows (`SET NULL`); `stage_evaluations` cascade.

### Workspaces, jobs and the queue

- A request names its workspace (`X-Workspace`, `?workspace=` on the socket, else the
  account's `active_workspace`); `require_member` resolves it once and hands `Access.ws` down.
  Switching workspace clears the client's query cache and resets the run store.
- `deps.py` is an LRU (8) of `RuntimeContext`s keyed by slug; `deps._lock` is held across
  `initialize`. Runtime components keep no per-run state on `self` (two jobs of one workspace
  may share a context).
- A `Job` carries workspace and author; events are stamped by the bus; `/api/jobs/{id}` 404s
  across workspaces.
- **The queue serialises per backend lane**: `local` (Ollama, capacity 1, not a setting) and
  `remote` (Cerebras, `CEREBRAS_MAX_CONCURRENT_JOBS`, default 4 — safe only because the
  ledger books claims). Only generative models reserve a lane (never the embedder/guardrail).
  A blocked job holds one slot of each of its lanes. `backends_for` fails closed (reserve
  both). A `generate` job's writer lane comes from the commission's model; an `evaluate`
  job's from `evaluation.local_model`.
- `GET /api/pipeline` reports lanes: `busy` means FULL; `current_job` is the oldest job of
  YOUR workspace. The idle GPU clock counts every lane.
- **Cancellation is cooperative at token granularity**: `inference.generate()` streams
  internally and emits nothing, and closing the stream stops the engine. `request_cancel`
  returns at once; SIGKILL escalation runs on its own thread. Waits are sliced into one-second
  checkpoints. A stop button stops every run its sibling button started.
- Every validated item is a JSON file, `<workspace>/generations/user_<id>/<id>.json`
  ([server/generations.py](server/generations.py)), written the moment it validates
  (`on_accepted`) with `json_io.write_json`; one file per exercise, so concurrent jobs never
  share one. It keeps `commission` (as asked; `think` a level or a bool) beside `resolved`
  (targets, `assumed_known`/`forbidden` and the closure rule, few-shot with origins, ruling,
  `avoid`, model and effort that ran, engine, lane, prompt language), the artifact hashes
  (`inputs`), the settings that shape a statement, the version, the accepted attempt's prompt
  and the output. The library hands it over as `GeneratedVariant.prompt`/`.provenance` and
  writes nothing. Id = `<UTC>-<job>-<index>`, checked by regex on every route. **An exercise
  is private to its author**: the author's id (never the username) names the directory, `user_<id>/`; no
  workspace scope, the same 404 for others' and malformed ids. Format 0 is a row exported
  from the retired table: what it never kept is null, never reconstructed.
- Deleting is the admin panel's (`DELETE /api/admin/workspaces/{slug}`, `.../artifacts/...`).
  `installation.destroy` refuses any path that is not a direct child of `WORKSPACES_DIR`; the
  tree goes before the row. **A workspace deletion that leaves no other member takes its tree
  too; if others remain, the files stay** — the generated exercises with them. Emptying a
  stage never touches `.history/`.
- The API owns the SSH tunnel to the GPU box (`server/tunnel.py`, system `ssh -N -L`,
  `BatchMode=yes`, watchdog with backoff).
- Job logs are **files**, `logs/<slug>/jobs.log` (one shared sink per workspace, filtered by
  thread; the build worker writes the same file). No `log` event on the bus, no log viewer.

### Build chain and approvals

- `review.ARTIFACTS` order: profile → graph → bank. The profile leads because taggability
  needs an APPROVED profile. `GATES` answers «are X's upstreams approved?»;
  `NEEDS_APPROVED` gates `review_taggability` on the profile.
- A build writes exactly one artifact (+ its cache). `server/jobs/chain.py` chains the graph
  build into describing concepts (condition: the graph exists) and the taggability review
  (condition: approved profile); an unmet condition skips, never fails.
- **The raw documents are an upstream**: `jobs/handlers._build` records the slot's documents
  (name, size, mtime) in `instance/.built_from.json`; a stage built from documents its slot no
  longer holds is stale with the drift named, and offers «Volver a construir» (the only
  rebuild offered anywhere). `approvals.RAW_SOURCE` is the one table of which slot feeds which
  artifact. A stage with no record is never stale for its documents.
- **A build waits for a LIVE transcription of the slot it reads** (409 outside `force`),
  because both write the same page cache. `singletons.transcribing(slug, slot)` is the one
  reading. This is not a gate on transcription having happened.
- Every hand edit withdraws the stage's approval on the server; the client never reopens.
- The bank checkpoints per document into `instance/.exemplars_bank.building.json` and writes
  `exemplars_bank.json` once at the end, starting empty (`C001`); cancelling loses the run;
  the parent sweeps the working file.

### Transcription (`server/raw_data.py`, `entrypoints/transcribe.py`)

**An accelerator, never a gate**: every builder keeps its own conversion phase; `transcribe`
has no `GATES`/`NEEDS_APPROVED` entry, nothing chains after it, and it writes no artifact.
Both raw slots use the same VLM page route (quality over speed).

- Per document state `done`/`pending`/`stale` **with the reason** (model, DPI, OCR, deck,
  cleanup…). Hand-edited pages win over the model and survive every build; editing drops only
  the two seam records around the page. The last page cannot be deleted.
- Page seams: deterministic first, the `transcribe_seam` model only classifies ambiguous ones
  and never rewrites; fails open. Seam decisions are cached in `_meta.json`.
  `<!-- page N -->` marks only paragraph seams.
- **A document is its bytes**: the same PDF anywhere in the installation arrives read
  (`pages.reuse_key`, `adopt_pages` copies — never links — pages from a donor with an
  identical fingerprint minus `source`), at upload and at the head of `transcribe_slot`.
- **All PDFium calls go through `pages._PDFIUM_LOCK`** (process-wide RLock, released between
  pages, documents closed under the lock). PDFium is not thread-safe and one corruption
  poisons the process.
- Scanned pages (no text layer) go as JPEG q90; renders are capped at two A4 areas; MIME is
  read off the bytes. A failed page of a finished PDF is re-read on its own later, unless
  pages were inserted/deleted by hand (`restructured`) or the page count changed.
- **Truncation and loops**: `TRANSCRIBE_MAX_OUTPUT_TOKENS` (4096) caps each answer;
  `inference.generate(stop_on_loop=True)` cuts a repetition loop in the stream
  (`core/repetition.py`). An unfinished answer is retried ONCE with a note naming the loop;
  if still unfinished the page keeps the text before the loop under the failed-page marker
  (pictures are not salvaged). Cached pages are scanned for loops and re-read. There is **no
  prompt version**: a prompt change re-reads nothing (`RETIRED_FIELDS` drops old fingerprint keys).
- Office files: Docling translates the text; EMF/WMF are rasterised through LibreOffice on a
  copy first (`source_docs/office.py`, PNG filter, two passes at 4×, cropped); each body picture
  is **transcribed** (never merely described) with the page model under `IMAGE_RULES`, cached
  by content hash workspace-wide (failures never cached; `EMPTY_IMAGE_MARK` cached and leaves
  nothing). Header/furniture pictures are never read.
- **A deck is one page per slide**, each with its speaker notes quoted below as a blockquote
  (`wording.speaker_notes_block`), read with python-pptx, no model call; seams between slides
  are fixed paragraphs.
- **Diagrams are transcribed as Mermaid** (`IMAGE_RULES`: labelled nodes and edges → a fenced
  mermaid block of the fitting type; surrounding text outside the block; big or illegible
  trees → `[figura: …]`).
- Docling's own escapes are undone on its output only (`markdown.undo_converter_escapes`),
  outside fences; never on a transcribed page or a hand-written `.md`.
- Routes under `/api/raw/{kind}/transcription…` are declared ABOVE `/{kind}/{name}`. Names
  from requests are checked against the slot's actual files.

### Curriculum (`server/curriculum.py`)

Host state (`instance/.curriculum.json`), validated against the graph on read. **Absent
falls back to the file, `[]` means no restriction.** `resolve()` closes the list in force
downward (prerequisites included) and the row records what ran. No screen edits the file
any more; a commission picks its own covered concepts. `GenerateForm`'s `assumedKnown`/
`notYetTaught` mirror `variatio.assumed_known`/`forbidden` — edit the Python first.

### Which model writes a variant

`generation.models` is the offered shortlist (engine-scoped, `min_items=1`);
`VARIANT_GENERATION_LLM` is its first entry and is what the CLI and the evaluation use. The
commission picks the model (checked twice: 422 at submit, `entrypoints.resolve_generation_model`
in the handler). Every offered model gets the context override and is protected by
`required_models()`. `generation.fixed_effort` + `generation.fixed_effort_levels` let the
installation lock and set a model's effort; `entrypoints.resolve_generation_effort` has the
last word; reasoning switched off is never turned on. `GET /api/health` carries
`models.offered`.

## The library

### Artifacts

Each artifact has a stem threaded through by role: `raw/raw_<stem>/` →
`variatio/builders/<stem>_builder` → `instance/<stem>.json` → loader.

- `knowledge_graph.json` — curated schema (`concepts_by_domains`,
  `generic_non_taggable_concepts`, `taggability_reviewed`, typed `relations`). The number and
  types of relations are variable; the loader stays relation-agnostic and cycle-checks
  `acyclic` relations. The builder only writes `knowledge_graph_autogenerated.json`; curation
  into the curated file is manual; `initialize` falls back to the draft with a warning.
- `exemplars_bank.json` — example items, plus the tagger's `concepts`/`primary_concept`.
- `exemplars_profile.json` — the content schema (`fields`, `general_generation_rules`,
  `primary_field`, `embed_fields`); validated into a runtime Pydantic `ContentItem`. This is
  how a use case is instantiated. The profile builder is a draft generator and unstable.
- `content_context.json` (+ `_autogenerated` draft; curated wins) — the subject in prose plus
  three named facts (`subject`, `educational_level`, `language_of_instruction`). **It has no
  builder of its own**: the graph and profile builders each synthesise it in a final
  `context` phase. `prompt_block()` is the only renderer; capped at
  `CONTENT_CONTEXT_MAX_CHARS` (900); it feeds the description fingerprint. Read-only on
  screen (under «Mi perfil → Espacios de trabajo»); `PUT /api/context` still exists.
- `instance/locale.json` — the workspace's prompt language, chosen at creation and never
  after (relation labels are baked into the graph).

### Builders (`variatio/builders/`)

`entrypoints/build.py` is the only importer. `source_docs/` holds all document plumbing
(`files`, `markdown`, `chunking`, `pages`, `office`); only `pages.py` talks to a model.
Builders use `inference.generate()`, never `generate_stream()` (a build runs out of process).

**Knowledge graph** ([knowledge_graph_builder/](variatio/builders/knowledge_graph_builder/)):
extract → clean → curate, handing dicts in memory; only `curate()` writes.

- Relation vocabulary is `instance/relations.py` per language. The `verbose` labels
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
- `KG_BUILDER_MERGE_QUALIFIER_PATTERN` and the unclassified name fail silently if removed.
- Progress is a weighted phase plan (`BUILD_PHASES`); the client reads it over REST.
  `_StepHandle.start()` reports the in-flight unit as not done; `tick` means done.

**Exemplars bank**: batches markdown with one-block overlap, extracts with an LLM, dedups by
folded primary field, validates against `ContentItem`. **With a remotely served model it asks
WITHOUT a grammar** (`_grammar_costs_the_text`): Cerebras' constrained decoding mangled every
non-ASCII character into `\u00XX` garbage. The repair drops its grammar too. The prompts ask
for non-ASCII characters written as themselves.

**Profile**: `guarantee_difficulty` runs on every consolidation route.

### Difficulty

Every modality carries a difficulty field; **the ladder is shared, only the criterion is the
modality's own**. The artifact shape is an ordinary field (`schema.enum`, `description`,
`guidance.extraction`, `decided_by: "user"`). The field name is the prompt set's
(`nivel_dificultad` / `difficulty_level`); writers resolve it via `locale.difficulty(ws)`,
readers via `ItemType.difficulty_field`. Rank = position in the modality's own enum;
unranked sorts last. The criterion has a shape the client splits (`«rung»:` markers,
`web/src/lib/difficulty.ts`, needs ≥2 marks else shown whole). `guarantee_difficulty` is a
floor, never a rewrite; it keeps the field out of `embed_fields` and writes it last. It is
not a row in «Campos de …»; the generate form asks «¿De qué nivel?» regardless of
`decided_by`, and admissibility owners include it regardless too.

A modality may also declare **one variant decision field** (e.g. diagram kind) when its
exemplars split along a discrete form of the deliverable.

### Taggability

Not part of the builder: a job (`review_taggability`) judged per domain against the
profile's modalities and real bank samples; operative test is discrimination, tie-break
«exclude when in doubt». A build writes `taggability_reviewed: false`; the library states the
flag and does not enforce it. `entrypoints/taggability.review_taggability(ws)` assembles it and
returns data; the handler writes through `kg_edit.set_non_taggable`.

### Entry points (`variatio/entrypoints/`)

Mechanism, not policy: return data, raise `MissingArtifactError`, never print, never exit,
never auto-trigger heavier phases, and never import the engine. `_artifacts.py`,
`transcribe.py`, `build.py` (profile before bank), `initialize.py` (loads artifacts, builds
embedder, tags only pending items when `tag=True` — tagging BEFORE enrichment is the warm
start; initialize once per process), `descriptions.py`, `taggability.py`, `generate.py`.

### Runtime components (`variatio/runtime/`)

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

### Prompts and wording

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

### Logging

loguru configured once in `variatio/__init__.py`. **`variatio/` logs in English; `server/`
and `evaluation/` in Spanish.** Format `[scope] Message`, no counters in the bracket, `«…»`
around user text, `'…'` around models/paths. Nothing inside a per-element loop logs at INFO —
use `progress.step(...).tick(detail=…)` or `debug`. A fact is logged by one layer. Only
`docling` is silenced.

### Pipeline shape

`cli.main()` → `require_engine()` → (`build_missing()`) → `initialize()` → `generate()`.
Components never persist; every write goes through `json_io.write_json` (the only writer of
persisted JSON: mkdir, `ensure_ascii=False, indent=2`, atomic `.tmp` replace — approval hashes
are hashes of these bytes).

## `evaluation/` — the TFM's study, outside the system it measures

A top-level package, always mounted. **`evaluation` imports `variatio`, never the reverse**
(one exception: the settings registry's optional import); pinned by
`tests/evaluation/test_evaluation_boundary.py`. `evaluation/__init__.py` never imports
`evaluation/api/`, so `import evaluation` stays free of FastAPI/SQLAlchemy. It is attached in
`server/app.py` (`evaluation.api.install(app)`), never from `server/routers/__init__.py`.

- **Arms**: `naive` (commercial chain `gemini → mistral → groq`, no `response_format`, no
  retries — the chain is the retry; provider and model id are stored per session), `rag`
  (retrieves 3 + 3 chunks over the RAW documents read with a plain extractor — `pypdf`,
  python-docx/pptx — never the pipeline's transcription, the bank, the profile's prose or the
  graph; gets the naive prompt plus the bare output schema), and `system`.
- Both baselines receive `content_context.prompt_block()` under the three facts.
- **A session is two cards: the system's and one rival** (`naive` or `rag`) drawn by the seed
  in `draw_session` (rival, order, `think`). Only the two drawn arms are generated.
  Three-card sessions recorded earlier are read, never rewritten.
- **One scenario per session**: drawn once by a short call and placed in both prompts, unless
  the free text already fixes a theme (`SCENARIO_NONE`). No scenario field on the form.
- The two local arms are written by `evaluation.local_model` (admin setting; null = the first
  offered generation model); no request carries a model for `evaluate`.
- After all arms, `_tag` tags every proposal; `off_limits` = tagged ∩ forbidden ∪ lexical
  mentions, drawn on every revealed card.
- **Everything blind is collected before the reveal**: per-card triage (`yes/partly/no`,
  stored by position), forced choice, decline (never a preference), then reveal, then the
  optional four-scale rubric about the system's exercise. The evaluator never sees aggregate
  scores. Time-on-task is recorded, never shown.
- Assignment of sets to evaluators by hand from the admin panel, each copy with a fresh
  shuffle; cross evaluation is behind `CROSS_EVALUATION` (off).
- Statistics are stdlib math: pairwise duels (exact binomial, Wilson), position bias on two
  positions (df 1), and **Scott's π** (not Cohen's κ) over evaluator pairs sharing a set.
- **Every fixed route is declared above `/evaluations/{session_id}`** (FastAPI matches in
  order); `test_route_order.py` checks every router.
- `evaluation/api/instruments.py` and `stage_instruments.py` are the single homes of what is
  asked. The **stage questionnaire** (one per construction step, keyed by artifact hash
  resolved server-side, `stage_evaluations`) is a Likert form: five statements on shared axes
  (`precision`, `recall`, `function`, `effort`, `overall`), 1-5 agreement, 5 is best,
  `VERSION = "4"`; earlier wordings are never pooled. `curated` records whether the answerer
  corrected the stage (nullable, only climbs). «Opened» is stamped when the form unfolds.
- The admin «Evaluaciones» tab filters by profile → account → workspace, one «Por evaluador»
  table, then «Fase de construcción» and «Fase de pruebas» blocks with CSVs; an evaluator's
  records can be withdrawn (`DELETE /api/admin/evaluations/records`).
- **The memoria must record** which engine, prompt language, first offered model, instrument
  version and arm configuration produced each result; there is no version column, so change
  dates are boundaries.

## The web interface (`web/`)

### Material and tokens

[web/src/index.css](web/src/index.css) holds shadcn token names. **The grid**: black ink on
white, `--radius: 0`, **`--primary` is the ink, not a hue**, so colour only appears where it
means something. Semantics encode position relative to the knowledge frontier: `--settled`
(behind you, grey), `--attention` (ultramarine, act here), dimmed/dashed (ahead),
`--destructive` (damage), `--evaluation` (deep green, the study). `--success/--warning/--info`
stay retired. Every value is measured: **`pnpm check:color`** is the gate (contrast, ΔE under
dichromacy, every `--X-foreground` against `--X`). A colour literal outside `index.css` is
invisible to it, so a foreground must be a token. Tint surfaces with `color-mix(in oklab, …)`,
never `oklch` (hue interpolation turns greens blue).

- `--arm-naive/--arm-rag/--arm-system` are the one categorical scale, order fixed, slots per
  entity, bars and rows only.
- Theme: three-state (`system`/`light`/`dark`), dark tokens only under
  `:root[data-theme="dark"]`.
- Typography: Archivo only, roles by width axis and weight; six ordered steps. Tutorial alone
  uses Literata (self-hosted — the CSP forbids external fonts).
- **Global `*` rules in `index.css` go in `@layer base`** or they silently override every
  Tailwind utility (this once disabled every `border-<colour>`).
- `vertical-align` on a `<tr>` does nothing; select the cells (`[&>td]:align-top`).
- `line-clamp-N` must never sit beside `block`.

### Navigation and the four steps

- [lib/steps.ts](web/src/lib/steps.ts) is the single home of the path: `STEPS` (raw
  material, profile, graph, bank, numbered 1-4 as «Fase de construcción») and `USES` (the two
  unnumbered doors of «Fase de pruebas»: «Generar ejercicios», «Evaluar el sistema»). The
  first not-done step is `now`; done steps show a bare tick, no box. Doors are half-dimmed and
  unclickable until construction is complete. Once all four are done and you are not on one,
  the phase folds into one pill. There is **no dashboard**: `/` redirects to the current step.
- A step with a running job spins a wheel (`stepBusy`); queued is never busy.
- Vocabulary seen by teachers: «Apuntes y ejercicios», «Tipos de ejercicio», «El temario»
  (the step; «concepto» for a node; «grafo» only for the structure), «Etiquetado», «leer»,
  «sirve de etiqueta», «asignatura» for a workspace, «ejercicio(s) generado(s)» for output.
  Identifiers, routes and keys keep their names. The app never narrates itself in the first
  person; the reader's own answers may be first person.
- Every URL path and guide slug is English.

### Stage screens (`StageGate`)

- An unbuilt stage shows its header and one central `xl` «Comenzar construcción» block
  (`BuildButton` decides every reason not to offer it; there is no rebuild except a
  document-stale stage). A stage opens in a read-only **review** state; «Quiero corregir algo»
  unlocks correction, with a sticky bottom bar carrying the save state and «Guardar los
  cambios»; «Continuar» (big, `--attention`) saves-and-approves and moves on. No «Aprobar» or
  «Reabrir». No tags or (i) beside a stage's title; the guide link sits under it.
- The stage questionnaire unfolds under its button at the foot of the artifact, on every
  built stage.
- A rebuild hides the old artifact without deleting it. A queued job draws no progress bar.
  «Pasos» of a build start folded, and nothing remembers the fold.
- `lib/queue.ts` is the single home of «is it waiting and behind what»; `isQueued` believes
  `queue_position > 0`; `waitOf` only when something is truly ahead.
- A screen finds its own job by kind (`useJobRun`/`useOwnJobRun`), never by `currentJobId`.
  «Generar» shows the run of this visit plus any still live.
- Deleting or switching workspace never calls `client.clear()` (it destroys the session
  query); the same applies to `useAdopt`.
- One `--attention` per screen, on the thing to act on. A control and a report never share a
  line. Fold, never drop, and never fold the only copy of something. An (i) and visible text
  never say the same thing.
- No build time estimates anywhere, in any form.

### Specific screens

- `/raw`: one row per document; multi-select delete; a finished origin is tinted with a
  filled tick; the foot offers «Continuar» once both origins hold something.
- Graph: three columns (list, concept card, fixed-size graph card) plus a full-width
  relations block for the chosen concept. The canvas viewer (`features/kg/graph/`) lays units
  out as syllabus-ordered regions, relaxes concepts in a worker (Barnes-Hut, deterministic),
  caches layouts per structure, and picks detail by on-screen distance. Units open collapsed;
  the per-row «sirve de etiqueta» switch is the only place it is set and never moves the row.
- Bank: seven rows a page, every collapsed row the same height, bounded cells, `table-fixed`,
  filters (search, modality, source, level, «Sin concepto»), no ordering control, no
  similarity scores, primary concept as a filled badge placed first. `ConceptBadge`/
  `ConceptChip` are the two ways to draw a concept; badges truncate with a `title`.
- Generate: numbered steps; the curriculum box inside «¿Qué hay que practicar?» (no switch;
  in force when non-empty; marking a concept marks its prerequisites, and the closed list is
  what runs); prerequisites of targets are marked, never locked; exemplar-scope switch
  defaults to «Solo conceptos con ejemplos» each opening; model cards above the reasoning
  block (hidden with one model); a refused instruction locks the button until the text
  changes; after a run, «Variar el encargo actual» / «Empezar desde cero», both clearing the
  previous batch.
- Evaluation: two blind cards at fixed height scrolling inside, «Ver completo» opens the
  reading dialog; after the reveal the same grid, collapsed, then the verdict band, then the
  rubric section. The screen reopens on the form, not the last session.
- Formulas render with KaTeX (`TeX`, tokenised before markdown, strict `$` rules,
  `throwOnError: false`); diagrams with Mermaid (lazy, painted in tokens, invalid ones show
  source and error). `lib/diagram.ts`'s `DRAWN` table decides which Mermaid kinds are drawn
  AND bundled (`web/vite/mermaid-subset.ts` fails the build if Mermaid's shape moves). One
  KaTeX version is forced via `pnpm-workspace.yaml`.
- `Progress`: total zero reads empty, unknown total sweeps (`barFill`).
- The tutorial is six full-window slides with no header, edge rails for navigation,
  justified prose from `sm` up; it draws the app as it is.
- The in-app guide (`/guide`) is user-facing copy: a behaviour change is not finished until
  its section is. Every screen links its section via `GuideLink` typed by `GuideSlug`.
- «Administración» lives in the account menu (soft red), before «Tema», before «Salir».
  «Motor» tab: left column measures, right column sets; one save bar; the guardrail and
  embedder models are read-only.

### Client rules

- i18n: `es.ts` is the source, `en.ts` is typed against it (missing key = `tsc` error), `es`
  eager and `en` lazy. `pnpm check:i18n` catches untranslated literals and missing guide
  sections. **Delete catalogue keys nobody reads** (prove it, delete from both, let `tsc`
  answer). Strings the server sends by stable key are translated client-side
  (`lib/names.ts`, `lib/raw.ts`, `lib/evaluator.ts`) with the server string as fallback.
- API payloads are read defensively: an older API must degrade the screen, never blank it.
  A panel that cannot load says so.
- `index.html` revalidates, `/assets` is immutable; a stale-chunk error reloads once.
- `pnpm check:ui`: no raw Tailwind scale sizes, no unlabelled control, no raw `<table>`.
- A vocabulary sweep is verified in the browser, not by a green suite.

## Closed decisions (do not revert without explicit user request)

Each line is a rule; the reason behind it is in the commit that introduced it.

**Structure**
- `evaluation/` stays outside `variatio/`; one-way import; not made removable.
- `builders/` ↔ `runtime/` ↔ `entrypoints/`; root holds three files; setting keys (e.g.
  `models.phases.concept_tagger`) and on-disk names (`.review_state.json`) do not follow
  module renames. Renames are done per importer, never with a global `sed`.
- No default workspace; no reserved slug; a path is never a defaulted argument.
- Settings in the registry + `config.json`; one writer (`store.write_file` → `json_io`);
  dotenv loader lives in `core/dotenv.py`.
- One writer of persisted JSON: `json_io.write_json`.
- Knowledge-graph extraction lives in this repo; no `kg-builder` dependency; the web app is
  the only graph viewer.
- A build writes only its final artifact; draft and curated stay two files. The bank's
  building file is the one exception.
- Taggability is not part of the builder; the graph build chains it (and describing) at the
  job layer; no `GATES` or `JOB_ARTIFACT` entry for it.
- Content context is its own artifact, written by the other two builders; keep the three
  named facts and the single renderer.
- Transcription is an accelerator and a step of `/raw`, never a gate or a stage; both slots
  use the VLM page route; no PDF→DOCX conversion; Office pictures transcribed with the page
  model (no separate setting); metafiles rasterised through LibreOffice PNG export on a copy.
- A build waits for a live transcription of its slot (a concurrency rule, not a gate).
- Strings whose language must match the workspace live in `wording/`.
- Screening is one package with two calls in fixed order (guardrail first); the sequence
  exists once.

**Prompts and the graph**
- Two prompt sets per workspace; JSON keys never translated; sets interchangeable.
- UI language belongs to the account, prompt language to the workspace, and
  `language_of_instruction` to the corpus — three different axes.
- Every modality carries a difficulty; shared ladder, local criterion; the criterion's
  `«rung»:` shape is legislated by the prompt.
- `guidance.generation` is hand-written only; modality rules carry generation.
- Prerequisite lists are transitive closures bounded by the curriculum, with opposite set
  operations; without a curriculum, later concepts may be used but not practised.
- The hierarchy is one relation (`se_engloba_en`); `relacionado` stays in embeddings; don't
  wholesale-regenerate descriptions without benchmarking retrieval.
- No anchoring beats a false one. Descriptions are impersonal and grammar-constrained.
- The free-text field is a four-slot catalogue, judged after the guardrail, failing open,
  verified against derived owners.
- Diagrams are transcribed as Mermaid; the merge prompt treats grammatical variants as one
  concept; the profile may declare one variant decision field per modality.

**Models and inference**
- Open weights only; the optional `cerebras+ollama` engine is the one hosted exception and
  is per-installation. No other hosted providers without asking. No fallback to Ollama when
  the Cerebras budget runs out.
- Nothing is warmed; `ensure_models` only checks and pulls.
- No main model; every phase names its own.
- Judging/generating default `qwen3.8:27b-q8_0`, reasoning default `low`; `max` is `high` on
  that model; `qwen3.6:35b-a3b-q4_K_M` is broken (illegal memory access) — never re-add.
- The domains naming call runs without reasoning; the phase context window is 65536.
- Embedding model fixed at `qwen3-embedding:4b`.
- The Cerebras throttle is a hard cap no header may raise; the gate books claims.
- No grammar to a remote model on the bank extraction (or its repair).
- The commission chooses its writing model from the offered list; rows record it.
- Queue per backend lane; local capacity 1 forever; remote capacity safe only with the
  ledger's lock and claims.
- `inference.generate()` streams internally and is interruptible; the stream is closed on
  abandon; waits are sliced.
- The idle unload clock counts every lane; not replaced by a shorter keep-alive.
- A transcription answer at the output cap or in a repetition loop is a failed page (after
  one noted retry, salvaged up to the loop); there is no prompt version.
- gpt-oss is not used; no code names it.

**Identity and access**
- Invitation-only sign-up; own auth; no JWT; username identity, email optional.
- Membership checked on every route; admin bypass in one place.
- Invitations and membership managed by the admin alone; links sealed, not stored in clear.
- No «forgot password» on the login screen; no password generator; no session list.
- The evaluator never sees the evaluation's score; blind instruments come before the reveal.
- A session shows the system's proposal and one seed-drawn rival.
- Deleting workspaces/artifacts is the admin's and takes the files; a last-member deletion
  takes the tree; `.history/` is never emptied by it. CORS off.
- Exercises are private to their author.
- Generated exercises are files in the workspace, one per exercise in the author's `user_<id>/`;
  the database keeps none of them. The library returns how an item was made; the server
  writes it. `uv run variatio generate` (the CLI) saves nothing.

**Interface**
- The palette is measured; `--primary` is ink; `--radius: 0`; arm colours fixed; theme
  three-state.
- The bar is the path: four numbered steps and two unnumbered doors; no dashboard; the rail
  is gone.
- View and correct are two moments; «Continuar» closes a stage; no «Aprobar»/«Reabrir»; no
  rebuild except for document drift.
- A queued job is not a running one. No time estimates. No «loading model» signal. No log on
  screen. No run drawer.
- Generate screen belongs to the visit. Live feed window of ten admitting one row at a time
  (`features/bank/window.ts`). Zero total ≠ unknown total. KaTeX for formulas.
- The raw material is its own screen; one row per document; nothing announces completeness
  except the finished-origin tint and the closing block.
- A control a teacher cannot decide is not offered (artifact fields and endpoints remain).
- No (i) beside a stage title; an (i) and visible text never say the same thing.
- The mark is three equal squares (settled, attention, outline).
- Every URL path is English. A refusal names the move out of it (`ChainGate`).
- The exemplars profile is edited through the form alone.

## Code conventions

- **Stepdown order**: a function sits above the ones it calls; banners, data classes,
  dunders and anything with a registering decorator (routes!) never move. Measure before
  reordering; a change that does not reduce inversions is churn. `tests/`, `web/`,
  `migrations/` and `db/models.py` are out of scope.
- Every module, class, function and method has a docstring: one imperative sentence (or noun
  phrase), then prose only for invariants, constraints and measured reasons. No
  `Args:`/`Returns:` sections.
- Comments are rare, English, and about one statement; narrative belongs in this file.
- Spanish survives only in string literals (UI copy, registry `doc=`, server/evaluation logs,
  error messages).
- Built-in generics (`list[str]`, `str | None`), `Callable` from `collections.abc`; no
  `typing` imports. No pandas in core. No multi-LLM validation frameworks or agent graphs.
  Heuristics first, LLM only on genuinely ambiguous input.
- Incremental, surgical changes; no speculative abstractions.

## Notes for working in this repo

- Gitignored: `/raw*`, `web/node_modules`, `web/dist`, `/workspaces/` in full (the repo ships no
  instance), `logs/`, `/.cerebras_budget.json`, `/.invite_link_key` (a secret; back it up
  beside `.env`).
- `config.json` at the root is versioned and holds no secrets; deleting it falls back to
  registry defaults.
- The working language with the user is Spanish; code, identifiers, comments and
  `variatio/` logs are English.

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
- `pending_ids()` treats an empty `concepts` list as untagged, so rejections are retried.
