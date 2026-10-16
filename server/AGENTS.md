# AGENTS.md — `server/` — the API

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Rules for the server outside its subpackages: the database, how a request finds its subject,
and the generated exercises. What every area stands on is `core/AGENTS.md`, identity
`auth/AGENTS.md`, the subjects of an account `workspaces/AGENTS.md`, the build chain
`pipeline/AGENTS.md`, step 1 `raw/AGENTS.md`, step 2 `kg/AGENTS.md`, step 3 `bank/AGENTS.md`,
«Clase» `classroom/AGENTS.md`, the queue `jobs/AGENTS.md`, what the tutor and the chat share
`conversations/AGENTS.md`, and the transcription `variatio/documents/AGENTS.md`.


## Routes and where a function plugs in

- `server/routing.py` holds `ROUTERS`, the order the server's own routers are mounted in,
  and is the one module that imports a route module (an import contract with no exception: a
  function reads an area's services, never its routes). The route comparison of a phase reads
  `app.routes` whole.
- The server's layers are an import contract too: composition (`app.py`, `routing.py`, `cli/`),
  `routers/`, `bank/`, `kg/` and `raw/`, `classroom/`, `pipeline/`, `auth/` and `workspaces/`
  (no two of one group import each other), then `conversations/` and `generations.py`, then
  `core/`, then `jobs/`, then `db/`; each imports only what is below it. A route module is a
  leaf and may import any layer; the modules still at the root are outside the order until
  their area exists.
- The registries a function fills at its install live in `jobs/catalogue.py`: `HANDLERS`,
  `FEATURE_OF`, `ADMISSIONS`, beside `PRIVATE_KINDS`, `STUDENT_KINDS` and `JOB_CLASS`. The
  construction's handlers join `HANDLERS` at `pipeline/jobs.install()`, which `app.py` calls
  as it installs each function.

## Database (`server/db/`)

Postgres 16 + SQLAlchemy 2.0 + Alembic, all under the `server` extra; `import server` works
with no database. `Json = JSON().with_variant(JSONB(), "postgresql")`.

- **The ORM models describe what the migrations built**; `alembic` autogenerate against the
  live schema must report zero differences. Fix drift in the models, never with DDL.
- The pool keeps `DATABASE_POOL_SIZE` (30) connections and opens `DATABASE_MAX_OVERFLOW` (30)
  more on demand (`session._pool`; SQLite keeps its own). Postgres's `max_connections` must
  cover the sum over every process sharing it (prod, the lab and dev share one server, at 100
  today).
- Artifacts are versioned rows keyed `(workspace, kind, stage, version)`; an unchanged hash
  reuses the existing row.
- **Reads come from files; writes are mirrored best-effort** (`server/db/mirror.py`) at three
  hooks: `pipeline/storage.write_json`, `pipeline/jobs._build`, `Approvals.approve/reopen`. A
  DB failure is one warning, never an exception. `.review_state.json` is the operational
  truth.
- `import_instance`/`export_instance` round-trip byte-identically; approval hashes are
  re-derived, never trusted.

## Workspaces, jobs and the queue

- A request names its workspace (`X-Workspace`, `?workspace=` on the socket, else the
  account's `active_workspace`); `require_member` resolves it once and hands `Access.ws` down.
  Switching workspace clears the client's query cache and resets the run store.
- Sync routes run in 200 AnyIO worker threads (`app.WORKER_THREADS`, set in `lifespan`; the
  default 40 queued a class's polls).
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
  workspace scope, the same 404 for others' and malformed ids. The one exception is the
  installation administrator, read-only and only from the panel
  (`GET /api/admin/workspaces/{slug}/generations`, `generations.list_all`, opened from the
  «Asignaturas» tab's «Ver N ejercicios» button); the author's own routes refuse the admin as anyone. A subject's
  teachers read FIGURES of their students' exercises — date, type, level, concepts — and never
  one exercise (`server/classroom/activity.py`, decided 2026-10-07). Format 0 is a row exported
  from the retired table: what it never kept is null, never reconstructed. A student (role
  `viewer`) reads their own exercise whole, solution included, but not the bank it was made
  from: `GET /api/generations/{id}` answers them with `provenance.prompt` null and
  `resolved.few_shot` as ids and origins (`consumers/generation/api/router.without_bank`), and a revealed
  comparison card answers them without `prompt` and `raw_response`.
- Deleting from the panel is the administrator's (`DELETE /api/admin/workspaces/{slug}`,
  `.../artifacts/...`), and emptying a stage never touches `.history/`. When a subject's
  deletion takes its tree is `workspaces/AGENTS.md`.

## Build chain and approvals

The chain of the three steps, its approvals and gates, and the construction's jobs are
`pipeline/AGENTS.md`.

## Closed decisions

One line per rule in force; the date, commit and reason of each are in
the root `DECISIONS.md`. Do not reverse one without the user's explicit request.

- D-114, D-116 — Deleting workspaces/artifacts from the panel is the admin's and takes the
  files; `.history/` is never emptied by it. CORS off. D-115, a last-member deletion taking
  the tree, is `workspaces/AGENTS.md`'s.
- D-117, D-118, D-119 — Exercises are private to their author; the administrator alone reads
  every account's, read-only, from the panel. A subject's teachers read figures, never an
  exercise.
- D-126, D-127 — Generated exercises are files in the workspace, one per exercise in the
  author's `user_<id>/`; the library returns how an item was made, the server writes it; the
  CLI saves nothing.
