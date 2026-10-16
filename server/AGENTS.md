# AGENTS.md — `server/` — the API

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Rules for the server outside its subpackages: the database, how a request finds its subject,
the bank's build, the generated exercises, the curriculum and the class activity.
What every area stands on is `core/AGENTS.md`, identity `auth/AGENTS.md`, the subjects of an
account `workspaces/AGENTS.md`, the build chain `pipeline/AGENTS.md`, step 1 `raw/AGENTS.md`,
the queue `jobs/AGENTS.md`, what the tutor and the chat share `conversations/AGENTS.md`, and
the transcription `variatio/documents/AGENTS.md`.


## Routes and where a function plugs in

- `server/routing.py` holds `ROUTERS`, the order the server's own routers are mounted in,
  and is the one module that imports a route module (an import contract; the functions'
  imports of `routers/exercises.py` and `routers/bank.py` are named exceptions that leave
  with the bank's area). The route comparison of a phase reads
  `app.routes` whole.
- The server's layers are an import contract too: composition (`app.py`, `routing.py`, `cli/`),
  `routers/`, `raw/`, `pipeline/`, `auth/` and `workspaces/` (neither imports the other), then
  `conversations/` and `generations.py`, then `core/`, then `jobs/`, then `db/`; each imports
  only what is below it. A route module is a leaf and may import any layer; the modules still
  at the root are outside the order until their area exists.
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
  one exercise (`server/activity.py`, decided 2026-10-07). Format 0 is a row exported
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

## The bank's build

- The bank checkpoints per document into `artifacts/.exemplars_bank.building.json` and writes
  `exemplars_bank.json` once at the end, starting empty (`C001`); cancelling loses the run;
  the parent sweeps the working file. **What a person added survives a re-extraction**
  (2026-10-14): the handler hands the build the bank's `manual` and `generated` exercises as
  a seed (`bank_edit.seed`, `artifacts/.exemplars_bank.seed.json`, `build_worker --keep`),
  the builder starts from them with their ids and tags and drops an extracted exercise that
  repeats one (`ExemplarsBankBuilder.build(keep=)`). One that no longer fits its type is put
  aside once the new bank is in place (`artifacts/.bank_set_aside.json`), and the bank's page
  offers it back, corrected through «Nuevo ejercicio» as it was (`POST /api/bank`
  `set_aside`), or lets it go. The confirmation of «Extraer el banco otra vez» says what is
  kept and how many collected exercises carry marks that only an identical statement keeps.

## Curriculum (`server/curriculum.py`)

Host state (`artifacts/.curriculum.json`), validated against the graph on read. **Absent
falls back to the file, `[]` means no restriction.** `resolve()` closes the list in force
downward (prerequisites included) and the row records what ran. The file is the subject's
«Avance de la asignatura» (decided 2026-10-06), set by its teachers in «Clase» (`PUT
/api/kg/curriculum`, closed under prerequisites as it is saved) and tinted on the syllabus.
**It bounds nobody** (the user's decision, 2026-10-07: a student who wants to run ahead of
the class may): a commission's own list replaces it, a student's as a teacher's. The generate
form starts with no curriculum and offers the progress as one press, «Usar lo visto en clase»
(`GenerateForm.classProgress`), drawn only when the progress holds something and disabled
while it is what is ticked; it ticks the progress's frontier (`prerequisites.frontier`), so
the selector marks the rest instead of drawing every prerequisite as a pick. `GenerateForm`'s
`assumedKnown`/`notYetTaught` mirror `variatio.assumed_known`/`forbidden` — edit the Python
first. **A group may follow its own** (2026-10-14): `class_groups.progress`, null while it
follows the subject's, validated on read the same way (`curriculum.of_group`, which says
`own`). `GET`/`PUT /api/kg/curriculum` take `group` (`follow_subject` hands it back); a
student reads their group's when it has its own, so «Usar lo visto en clase» offers it; the
activity's «sin practicar» reads the scope's.

## Class activity (`server/activity.py`)

What a subject's students do, for its teachers (the user's request and decision, 2026-10-07):
`/api/activity` (`auth.EDIT`; a student reads nobody's, their own included). **The week is
the unit**: ISO weeks, Monday to Sunday, UTC (`server/core/daily.py`); a past week is closed —
every message and exercise is dated, so its figures do not move — and the present one is open.
The history is the strip of weeks from the first with activity to now, an empty week kept.
`?student=<id>` narrows to one student (active or paused; anybody else is 404); a removed
student counts for nothing, a teacher's own files are not the class's. `?group=<id>` narrows
the class to one of its groups (2026-10-14): every figure, finding, week and «Quién …» row is
counted over its students, and «de la clase» reads «del grupo». A group's digest is its own
(`POST …/digest` with `group`, the job reading that group's messages alone, one per week and
group at a time, `analytics/digest/<week>.group-<id>.json`); without one the reading shows the
class's cut to the group's students, as for one student.

- **Counted by code, never read**: of a conversation, each student turn's date, its reply's
  kind (`on_subject` for theory/exercise/attempt/solution), the concept (chosen, else the
  reply's first focus) and `sent_back`; of an exercise, its date, type, level (the workspace's
  difficulty field, `locale.difficulty`) and concepts, and whether a conversation was opened on
  it. The tutor's half comes through `activity.TUTOR_READER`, which `consumers.tutor.api.install` sets
  (the server never opens the tutor's files); every file goes through `activity.cached`, keyed
  by modification time and size.
- **Findings** are typed by the server, each of one page (`area`: `tutor` — `asked`,
  `solutions`, and for one student `topic`, `reviewed` — or `exercises` — `unpractised`, with
  the course's progress only, and for one student `practised`; `idle`, `trend` and, for one
  student, `quiet` are counted in each area apart, at most `MAX_FINDINGS` per area), and
  worded by the client (`lib/activity.sayFindings`, `findingsIn`; a finding with no area is
  placed by its kind). A student row carries `message_days` and `exercise_days` beside their
  sum `days`; the first a teacher can act on is the
  screen's one `--attention`. Thresholds (`MIN_ASKERS` 3, `SOLUTION_SHARE` 0.4 over
  `MIN_SOLUTION_MESSAGES` 5) are placeholders until the pilot measures them.
- **The digest is the teacher's to ask for**, never written on its own:
  `POST /api/activity/weeks/{week}/digest` queues the tutor's `activity_digest` job (class C,
  private to its author, not behind the tutor's function — a teacher reads their class's
  whether or not the tutor is open to them; one per week at a time, 409 `digest_busy`; at
  least `DIGEST_MIN_MESSAGES` 10 messages about the subject). Its parameter is the week; it
  groups the week's messages by concept (the `tutor.digest_max_concepts` most asked, each
  with its latest `tutor.digest_max_messages`), reads their texts inside the job, and asks the
  `tutor_digest` call (`tutor.models.digest`, empty = the classification's model) for at most
  three themes per concept, one sentence of 20 words at most, with the numbers of the messages
  they cover. **Paraphrase only**: a theme that copies more than 8 running words of a message,
  names a student (whole name, username, or a part of 4 letters or more), is too long or covers
  nothing is asked again once with a note, then dropped (`consumers/tutor/digest.clean_themes`). Only
  step events cross the stream, the log says counts, and the file —
  `<workspace>/analytics/digest/<week>.json` — keeps the themes and REFERENCES to the messages
  (author, conversation, turn), never a message. One digest per week, of the class: a theme's
  figures are counted from its references over who is of the class now, and a student's
  reading is the class's digest cut to the themes their messages fall under, with how many
  are theirs.

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
