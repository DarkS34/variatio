# AGENTS.md

Guidance for coding agents working in this repository.

**How to read the rules.** This file holds what is true everywhere; each folder with rules
of its own has an `AGENTS.md` beside its code (the index is under *Where the rules live*).
`ARCHITECTURE.md` is the map. The *Closed decisions* are authoritative: if a request would
reverse one, push back and ask before implementing; each has an entry in
[`DECISIONS.md`](DECISIONS.md) with its date, commit and reason. Numbers quoted are
measurements; re-measure before changing what they justify. Do not create a `CLAUDE.md`:
Claude Code reads `AGENTS.md` only when there is none.

## Writing to the user

**Write every answer, explanation and detail for the user 80% of the way to ASD-STE100**
(Simplified Technical English). The user asked for this so that the text is clear at first
reading. The language stays Spanish; the STE rules apply to the Spanish text.

- Write short sentences: 20 words at most for an instruction, 25 for a description.
- Put one idea in each sentence, and one topic in each paragraph (six sentences at most).
- Use the active voice and the simple tenses. Say who does what.
- Use one word for one thing. Do not change the term for variety.
- Write an instruction as a command, one action per sentence, in the order of the work.
  Put the condition before the action it controls.
- Prefer common words. Do not use idioms, metaphors or filler.
- Write a technical name (identifier, setting, command) as it is. Explain it the first time
  if the user may not know it.
- Keep the articles and the connectors; do not write telegraphic text. Do not chain more
  than three nouns.
- Use a list for steps and for parallel items.

«80%» means that the rules guide the text but STE's dictionary does not bind it: when a
rule and precision conflict, precision wins. The rule covers what is said to the user in the
conversation (answers, summaries, plans, questions). It does not change code, commit
messages, UI copy or this file, which keep their own conventions.

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

- **`main`** is the complete system and the only branch (2026-10-16: `variatio-vanilla`, the
  library alone, was retired with no tag; ask before bringing a branch back). `uv sync --no-dev`
  without the extras installs the library alone. Production serves a separate worktree,
  `/home/deploy/variatio-prod`; deploying is the user's.

## Commands

Dependency management is **`uv`** (`pyproject.toml` + `uv.lock` + `.python-version`).

- `uv sync` — install (package editable).
- `uv run variatio <transcribe|build|init|generate|all> --workspace SLUG` — the library CLI
  ([cli.py](variatio/cli.py)). `--workspace` is **required**; there is no default instance.
  `transcribe` reads raw documents into pages (`--slot corpus|exemplars|all`) and is never
  chained by anything; `build` creates missing artifacts; `init` loads, tags, warms indices;
  `generate` (`-n`, `--concepts`, `--item-type`, `--fixed FIELD=VALUE`, `--omit FIELD`,
  `--curriculum`, `--instructions`); `all` = build missing + init + generate.
- `uv run system [serve|import-instance|export-instance|export-generations|usage|workspaces|create-workspace|db-check|create-user|users|grant|invite|class-link]`
  — API and admin ([server/cli/](server/cli/)). No subcommand means `serve`. `guarded()` wraps
  every command except `db-check`, `serve` and `usage` (which reads a file, not the database).
  `PROG = "system"` matches `pyproject.toml`.
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
- `uv run lint-imports` — the import contracts of `pyproject.toml`; `uv run pytest` runs them too.
- Web: `pnpm test` (vitest), `pnpm exec tsc --noEmit`, `pnpm build`, `pnpm check:color`,
  `pnpm check:ui`, `pnpm check:i18n`, `pnpm check:lazy` (after `pnpm build`),
  `pnpm check:layers` (app → features → components → state → lib; its list only shrinks).

`README.md` says how to run it locally. Deploying a change with a migration or a new
dependency needs `uv sync` and `uv run alembic upgrade head` before the restart.

### Dependencies

- **Licence**: the code is under the PolyForm Noncommercial License 1.0.0 (`LICENSE`, SPDX
  `PolyForm-Noncommercial-1.0.0` in `pyproject.toml` and `web/package.json`). A new dependency
  must allow that: permissive or weak copyleft (MIT, BSD, Apache, ISC, MPL, LGPL, EPL) is
  fine; GPL or AGPL would bind the whole work to its own terms — ask first.
- `dependencies` — runtime pipeline only (httpx, loguru, networkx, numpy, ollama, tqdm,
  json-repair, pydantic). Every name there must be imported by the runtime.
- `[builders]` — Docling (~700 MB), python-pptx, pypdfium2. Imported **lazily**:
  `documents/files.LazyConverter` opens Docling only at `markdown.to_markdown`'s
  `convert()`, and `pypdfium2` only inside `documents/pages/render.py`. Never move those imports
  to module scope. Importing anything under `variatio/` must not import Docling or torch.
- `[server]` — FastAPI, uvicorn, SQLAlchemy/Alembic/psycopg, argon2-cffi, cryptography
  (`server/auth/links.py` only), pypdf (evaluation RAG reader).
- `[dependency-groups] dev` — builders + server.
- **LibreOffice is a system dependency of the builders** (`soffice`, looked up at call time)
  for rasterising EMF/WMF metafiles in Office files. Without it those pictures read as
  `[IMAGEN NO LEGIBLE]`. The document reader of `/raw` uses it too, to export a Word file
  (Writer) or a deck (`libreoffice-impress`) to PDF; without it those documents open as text.

### Runtime prerequisites

`import variatio` is side-effect-free and never reaches `core.inference`; every model call of
the API goes through a job; nothing is warmed. The engines, the Cerebras ledger and Ollama are
in `variatio/AGENTS.md`.

## Where the rules live

The hard line: **`artifacts/` holds the instance definition (data), `variatio/` is the code
that produces and consumes it.** `consumers` imports `variatio` and `server`; neither imports
`consumers` back. The rules of each part are beside it:

- `variatio/AGENTS.md` (library), `variatio/documents/AGENTS.md` (transcription).
- `server/AGENTS.md` (database, subjects, build chain, exercises, curriculum, activity),
  `server/core/AGENTS.md` (contexts, environment, tunnel, the door), `server/auth/AGENTS.md`
  (identity, roles, classes), `server/workspaces/AGENTS.md` (a subject's life and tree),
  `server/pipeline/AGENTS.md` (the build chain, approvals, the construction's jobs),
  `server/raw/AGENTS.md` (step 1), `server/kg/AGENTS.md` (step 2),
  `server/jobs/AGENTS.md` (the queue), `server/conversations/AGENTS.md`.
- `consumers/AGENTS.md` and one per function: `generation/`, `evaluation/`, `tutor/`, `chat/`.
- `web/AGENTS.md` and `web/DESIGN.md` (read before any UI change), plus `src/features/bank/`,
  `src/features/class/`, `src/features/admin/`, `src/features/raw/`, `src/consumers/tutor/`,
  `src/landing/`.

## Logging

loguru configured once in `variatio/__init__.py`. **`variatio/` logs in English; `server/`
and `consumers/` in Spanish.** Format `[scope] Message`, no counters in the bracket, `«…»`
around user text, `'…'` around models/paths. Nothing inside a per-element loop logs at INFO —
use `progress.step(...).tick(detail=…)` or `debug`. A fact is logged by one layer. Only
`docling` is silenced.

## Closed decisions (do not revert without explicit user request)

The ones that hold everywhere, with their numbers in [`DECISIONS.md`](DECISIONS.md); each
folder's `AGENTS.md` lists its own. To change one, follow «How to change a decision» there.

- D-001, D-003 — The code is PolyForm Noncommercial 1.0.0 (from 1.171.0); the history is not
  rewritten to hide the MIT commits, and copies taken then keep MIT.
- D-004, D-007 — The functions live in `consumers/`, outside `variatio/` and `server/`;
  one-way import; the evaluation is not made removable. What the tutor and the chat share is
  `server/conversations/`.
- D-008, D-009 — `builders/` ↔ `runtime/` ↔ `entrypoints/`; root holds three files; setting
  keys and on-disk names do not follow module renames. Renames go per importer, never `sed`.
- D-010 — No default workspace; no reserved slug; a path is never a defaulted argument.
- D-011 — A workspace's artifacts live in `artifacts/` and their loaders in
  `variatio/loaders/`; an old tree is renamed the first time it is opened.
- D-015 — One writer of persisted JSON: `json_io.write_json`.
- D-216, D-230 — `entrypoints/` is the library's door; `builders/` and `loaders/` take a
  `Workspace` only for their own paths. Inside `variatio/` only `cli.py`, `builders/`,
  `runtime/`, `documents/` and `core/` import `core.inference`.
- D-220 — Closed decisions are entries of `DECISIONS.md`; each `AGENTS.md` keeps rule and number.
- D-222 — Work plans go in `plans/` (git-ignored); there is no `docs/`.
- D-225 — There is no guide and no tutorial; their text is in git history.
- D-223 — One `AGENTS.md` per folder for what is the folder's; this file for what holds
  everywhere. The why of a folder lives in its `AGENTS.md`, of a decision in `DECISIONS.md`.
- D-226 — Python import boundaries are import-linter contracts; the client's direction is
  `pnpm check:layers`. An exception is named in the contract, never added in silence.
- Decided on 2026-10-16, not yet applied (the refactor plan): D-227 the server by areas, D-229
  the client's types, hooks and primitives split.

## Code conventions

- **Stepdown order**: a function sits above the ones it calls; banners, data classes,
  dunders and anything with a registering decorator (routes!) never move. Measure before
  reordering; a change that does not reduce inversions is churn. `tests/`, `web/`,
  `migrations/` and `db/models.py` are out of scope.
- Every module, class, function and method has a docstring: one imperative sentence (or noun
  phrase), then prose only for invariants, constraints and measured reasons. No
  `Args:`/`Returns:` sections.
- Comments are rare, English, and about one statement; narrative belongs in the folder's
  `AGENTS.md` (D-223).
- Spanish survives only in string literals (UI copy, registry `doc=`, server/evaluation logs,
  error messages).
- Built-in generics (`list[str]`, `str | None`), `Callable` from `collections.abc`; no
  `typing` imports. No pandas in core. No multi-LLM validation frameworks or agent graphs.
  Heuristics first, LLM only on genuinely ambiguous input.
- Incremental, surgical changes; no speculative abstractions.

## Notes for working in this repo

- Gitignored: `/raw*`, `/plans/` (private work plans; there is no `docs/`), `web/node_modules`,
  `web/dist`, `/workspaces/` in full (the repo ships no
  instance), `logs/`, `/.maintenance.json`, `/.invite_link_key` (a secret; back it up
  beside `.env`).
- `config.json` at the root is versioned and holds no secrets; deleting it falls back to
  registry defaults.
- The working language with the user is Spanish, written as *Writing to the user* says;
  code, identifiers, comments and `variatio/` logs are English.

