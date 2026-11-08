# AGENTS.md

Guidance for coding agents working in this repository.

**How to read the rules.** This file holds what is true everywhere; each folder with rules
of its own has an `AGENTS.md` beside its code (the index is under *Where the rules live*).
`ARCHITECTURE.md` is the map. The *Closed decisions* are authoritative: if a request would
reverse one, push back and ask before implementing; each carries its reason. Numbers
quoted are measurements; re-measure before changing what they justify. Do not create a
`CLAUDE.md`: Claude Code reads `AGENTS.md` only when there is none.

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

## Working with agents (D-247)

The principle: every line of the repo has a human author who can explain it without looking
at the diff. A change the user cannot explain is not finished, even when the tests pass.

- **Implement, do not design.** The user defines abstractions, signatures, module boundaries
  and data models before code is written. When they do not exist, propose them in text and
  wait; do not implement.
- **Plan before code.** For any non-trivial task, say which files change, which decisions are
  taken and which trade-offs are accepted, then wait for explicit approval.
- **Small commits.** One conceptual change per commit, a diff of at most 150 lines excluding
  tests and generated files. A task that does not fit is split, and the agent stops after
  each part.
- **Never commit.** Leave the working tree ready, the `version` bump of `pyproject.toml` (and
  `uv lock`) included; the user runs `git commit`.
- **Close with a summary** of 3–5 lines: what was decided, why, what was left out, what the
  user should check. A task without one is not closed.
- **Existing tests are not changed to make them pass.** When a test contradicts the change,
  stop and explain. New tests go in a separate commit.
- **Self-review is not approval.** Approval comes from the user or a second model.
- **The manual zone.** Only `web/`, `migrations/` and `tests/` may be edited on the agent's
  own initiative, under the rules above. Every other path (`variatio/`, `server/` and
  the root files) changes only on an explicit instruction that names the file
  and the change; never on the agent's initiative, never «in passing».
- **Explaining.** When asked to explain, give the data flow, the invariants and the
  trade-offs, not lists of files.
- **The comprehension map**, `plans/mapa-comprension.md` (git-ignored), marks each module
  green (the user explains it without looking), yellow (explains it looking) or red (cannot
  explain it); the user reviews it every two weeks. Read it before a change: a red module is
  not extended until it is yellow; explain it instead.
- **Alarm signals.** Name one when it shows: a diff accepted unread, a bug fixed without the
  user knowing its cause, a commit that changes many tests at once, a module whose structure
  the user cannot justify. Then stop: a diff over 150 lines or a session over two hours waits
  for the next day or is split.

The numbers (150 lines, two hours, two weeks) are a starting point, adjusted after a month of
use, not before (adopted 2026-11-05).

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

`import variatio` is side-effect-free and never reaches `inference/`; every model call of
the API goes through a job; nothing is warmed. The engines, the Cerebras ledger and Ollama are
in `variatio/AGENTS.md`.

## Where the rules live

The hard line: **`artifacts/` holds the instance definition (data), `variatio/` is the code
that produces and consumes it.** `server` imports `variatio`, never the reverse; each function
has a library half in `variatio/functionalities/` and a server half in `server/functionalities/`. The rules of each part are beside it:

- `variatio/AGENTS.md` (library), `variatio/documents/AGENTS.md` (transcription).
- `server/AGENTS.md` (database, subjects, exercises), `server/core/AGENTS.md` (contexts,
  environment, tunnel, the door), `server/auth/AGENTS.md` (identity, roles),
  `server/workspaces/AGENTS.md` (a subject's life and tree), `server/pipeline/AGENTS.md` (the
  build chain, approvals, the construction's jobs), `server/raw/AGENTS.md` (step 1),
  `server/kg/AGENTS.md` (step 2), `server/bank/AGENTS.md` (step 3),
  `server/classroom/AGENTS.md` (people, groups, links, progress, activity),
  `server/admin/AGENTS.md` (the panel),
  `server/jobs/AGENTS.md` (the queue), `server/functionalities/shared/conversations/AGENTS.md`.
- `variatio/functionalities/AGENTS.md` and one per function: `variatio/functionalities/`
  `evaluation/`, `tutor/` and `chat/`, and `server/functionalities/generation/AGENTS.md`.
- `web/AGENTS.md` and `web/DESIGN.md` (read before any UI change), plus `src/features/bank/`,
  `src/features/class/`, `src/features/admin/`, `src/features/raw/`, `src/consumers/tutor/`,
  `src/landing/`.

## Logging

loguru configured once in `variatio/__init__.py`. **`variatio/` logs in English, but for the tutor's, the chat's and
the evaluation's library halves; those and `server/` log in Spanish.** Format `[scope] Message`, no counters in the bracket, `«…»`
around user text, `'…'` around models/paths. Nothing inside a per-element loop logs at INFO —
use `progress.step(...).tick(detail=…)` or `debug`. A fact is logged by one layer. Only
`docling` is silenced.

## Closed decisions (do not revert without explicit user request)

These are the only closed decisions. To change one, ask the user, then edit its line here in
the same commit as the code; git keeps the history. A number cited elsewhere (code, a folder's
`AGENTS.md`) names an entry of the old register: `git show 6698e16:DECISIONS.md`.

- **D-001, D-003 — Licence.** The code is PolyForm Noncommercial 1.0.0 (from 1.171.0); the
  history is not rewritten, and copies taken while it was MIT keep MIT. *Why:* free for any
  noncommercial use, never sold; a rewrite would not take MIT back from existing copies.
- **D-004, D-007 — Functions.** Each function has a library half in `variatio/functionalities/`
  and a server half in `server/functionalities/` (until 2026-11-08 both lived in `consumers/`);
  no function imports another, and what several use is `functionalities/shared/` on each side;
  the evaluation is not made removable. What the tutor and the chat share is
  `server/functionalities/shared/conversations/`, and the blocks of their system prompts are
  `variatio/prompts/<language>/conversation.py`. *Why:* they consume what the construction
  builds.
- **D-008 — Layout by artifact.** `variatio/` is being reorganised by artifact
  (`plans/plan-reestructura.md`; each part updates this entry). Today: `api/` is the public
  door; `inference/` is the engine boundary (`inference/__init__.py`) with the engines, usage,
  vectors and repair, a layer between `prompts` and `utils : settings : config`;
  `prompts/<language>/` holds each prompt set with its `wording.py` and `conversation.py`;
  `utils/` holds what knows nothing about the subject (paths, `Workspace`, progress, JSON I/O,
  the workspace's language in `locale.py`);
  `knowledge_graph/` holds the graph (`graph.py`), the subject's context (`context.py`), the
  relation vocabulary (`relations.py`), their build (`build/`), the concept descriptions and
  the taggability review, a layer between `retrieval` and `documents`;
  `exemplars_bank/` holds the bank's build (`build.py`), its tagging (`tagging.py`) and the
  profile (`exemplars_profile/`: `profile.py` and its `build.py`), a layer between
  `functionalities` and `retrieval`; `retrieval/` holds the two vector indices (`Embedder`);
  `functionalities/` holds one package per function (`generation/`, `tutor/`, `chat/`,
  `evaluation/`) and what several share
  (`shared/screening/`), the top layer below `api`; `documents/` and `settings/` keep their
  roles. The three builds take a `Workspace` only for
  their own paths; the package root holds
  `config.py`, `cli.py` and `__init__.py`. *Why:* a person new to the code finds a thing by name.
- **D-009 — Renames.** Setting keys, on-disk names, URLs and job kinds do not follow module
  renames; renames go per importer, never with a global `sed`. *Why:* a renamed key silently
  resets an installation's choice, and several module names name a second live module.
- **D-010 — No default workspace.** No reserved slug; a path is never a defaulted argument.
  *Why:* a component built without paths once wrote into another instance.
- **D-011 — Artifacts on disk.** A workspace's artifacts live in `artifacts/`; an old tree is
  renamed the first time it is opened. *Why:* «instance» named three different things.
- **D-015 — One JSON writer.** Every persisted JSON goes through `json_io.write_json`.
  *Why:* approval hashes are hashes of these bytes.
- **D-036, D-037 — Languages.** Two interchangeable prompt sets, `es/` and `en/`, with the
  same modules and signatures (pinned by test); the JSON keys a model emits are never
  translated. The interface language is the account's, the prompt language the workspace's,
  the language of instruction the corpus's. *Why:* the keys are the parsers' grammar, and what
  a person reads differs from what the model is told.
- **D-057, D-067 — Models.** Only open-weight models; the optional `cerebras+ollama` engine is
  the one hosted exception, and no other hosted provider is added without asking. The embedder
  is fixed at `qwen3-embedding:4b`. *Why:* the user's choice; a new embedder rebuilds every
  index, and the thresholds are calibrated on this one (top-1 18/18 against 15/18).
- **D-092, D-117, D-198 — Access and privacy.** Every route checks a membership row
  (viewer/editor/owner). A generated exercise and a tutor conversation are private to their
  author: anyone else gets the 404 of a missing one; the installation administrator reads
  conversations read-only. *Why:* a filter is not privacy, and a 403 confirms the id exists.
- **D-230 — Who calls the engine.** Inside `variatio/`, only `cli.py`, `functionalities/`, `retrieval/`,
  `documents/`, `exemplars_bank/` (its builds and tagging) and `knowledge_graph/` (its build,
  descriptions and taggability review) import `inference/`. *Why:* `api/`, `prompts/`,
  `settings/`, the profile reader (`exemplars_bank/exemplars_profile/profile.py`) and the graph's
  three readers (`knowledge_graph/graph.py`, `context.py`, `relations.py`) stay cheap to import and never call a model.
- **D-220, D-223 — Documentation.** This section is the only register of closed decisions. One
  `AGENTS.md` per folder holds that folder's rules and their why; this file holds what holds
  everywhere, at most 200 lines. *Why:* the old register (1 295 lines) read as a history, and
  `AGENTS.md` once grew to 192 KB in 14 days.
- **D-222, D-225 — No docs.** Work plans go in `plans/` (git-ignored); there is no `docs/`,
  no guide and no tutorial (their text is in git history). *Why:* `docs/` only held plans.
- **D-226 — Import boundaries.** Python import boundaries are import-linter contracts; the
  client's direction is `pnpm check:layers`. An exception is named in the contract, never added
  in silence. *Why:* nothing else checks the layers.
- **D-247 — Agents.** The agent implements; the user designs and commits (*Working with
  agents*). *Why:* every line has a human author who can explain it without the diff.

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
  registry defaults. `rates/<engine>.json` beside it holds the measured seconds per unit of
  the construction steps; an engine with no file shows no time left (D-241).
- The working language with the user is Spanish, written as *Writing to the user* says;
  code, identifiers, comments and `variatio/` logs are English.

