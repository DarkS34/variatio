# AGENTS.md — `server/jobs/` — the job queue

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Rules for jobs, lanes, priority, privacy of a job's events, cancellation, job logs and measured
usage.

## Jobs and the queue

- A `Job` carries workspace and author; events are stamped by the bus; `/api/jobs/{id}` 404s
  across workspaces.
- **A private job is its author's alone** (decided 2026-10-06): `catalogue.PRIVATE_KINDS` is
  `generate`, `evaluate` and `tag_item` (2026-10-14), and `tutor_turn` and `chat_turn` join
  at their functions' install. The bus stamps a
  private job's events with its author (`publish_job`; `Event.private`/`user_id`, never in
  `to_dict()`) and `bus.visible` lets them reach that account's socket only; a subscriber
  naming no account, or an event with no author, sees nothing of it. Every job route of the
  workspace answers another account the same 404 as a missing job (`Job.seen_by`), the
  admin's bypass included — the admin cancels from the panel's queue. `/api/jobs/current`,
  the socket's `jobs` snapshot and `/api/pipeline` (`current_job`, `queued`, `ahead`, `mine`,
  a lane's named holder) count and name only what the account may see. A build, a
  transcription or the tutor's criteria are the subject's: every member watches them.
- **A job whose author is a student of the subject is `redacted`** (set by the route from
  `access.role == viewer`, never by the client): the bus strips the `prompt` event's text —
  the event still travels, the screen's marker of a new item — and keeps only `ids`,
  `concepts` and `item_type` of `few_shot`, before the event is buffered. The exercise's
  file keeps everything. Events live in the bus's memory buffer alone: there is no
  per-job event log on disk (`.runs/` was removed on 2026-10-07; nothing read it).
- **Tokens travel in batches**: `progress.token_sink` returns a `TokenBatch` that sends at
  most one `token` event every 100 ms (the first at once; a change of channel flushes), and
  `inference.generate_stream` flushes it when the answer ends, cut short or not.
- **The queue serialises per backend lane**: `local` (Ollama, capacity 1, not a setting) and
  `remote` (Cerebras, `CEREBRAS_MAX_CONCURRENT_JOBS`, default 4 — safe only because the
  ledger books claims). Only generative models reserve a lane (never the embedder/guardrail).
  A blocked job holds one slot of each of its lanes. `backends_for` fails closed (reserve
  both). A `generate` job's writer lane comes from the commission's model; an `evaluate`
  job's from `evaluation.local_model`.
- **What waits goes out by class, then by arrival** (`jobs/priority.py`, decided 2026-10-06):
  A a tutor's or a chat's turn (~30 s, somebody waits in a chat), B a commission, a comparison or the
  tagging of the exercises a teacher just wrote (`tag_item`; somebody watches the bar or the
  concepts arrive), C everything else (`catalogue.JOB_CLASS`, a kind with
  no row is C; the tutor classes its two kinds at install). The class is the kind's, never
  the role's. AGING: B counts as A after `QUEUE_PROMOTE_B_AFTER_SECONDS` (90) and C as B after
  `QUEUE_PROMOTE_C_AFTER_SECONDS` (600), then as A after B's term (690 s). On the local lane
  background jobs hold at most `LOCAL_MAX_BACKGROUND_JOBS` (2) slots, counted by the KIND's
  class even after aging, and a job held back only by that cap reserves nothing; with
  capacity 1 it never acts. `queue_position` counts what goes out first on a shared lane,
  aging included, and `pending()` lists in that order; every dispatch pass restamps, since
  waiting moves positions with no event. The runner reads its clock from `_clock` (a test
  ages a job at will). The order does not pre-empt: a build already running on Ollama keeps
  the tutor waiting until it ends, so builds go outside class hours.
- `GET /api/pipeline` reports lanes: `busy` means FULL; `current_job` is the oldest job of
  YOUR workspace. A lane's holder travels as `kind` (named by the client, `lib/names.ts`) plus
  the server's `label`, both left out when the holder's function (`catalogue.FEATURE_OF`,
  which the tutor's kinds join at install) is closed to the account. The idle GPU clock
  counts every lane.
- **Cancellation is cooperative at token granularity**: `inference.generate()` streams
  internally and emits nothing, and closing the stream stops the engine. `request_cancel`
  returns at once; SIGKILL escalation runs on its own thread. Waits are sliced into one-second
  checkpoints. A stop button stops every run its sibling button started.
- Job logs are **files**, `logs/<slug>/jobs.log` (one shared sink per workspace, filtered by
  thread; the build worker writes the same file). No `log` event on the bus, no log viewer.
- **What a job's model calls cost is measured** (2026-10-15, the plan's phase 9;
  `variatio/core/usage.py`): the runner opens a meter around every handler, and every call of
  the engine boundary counts on the meters open on its thread — the prompt's tokens and the
  answer's, exact (Ollama's last chunk, `prompt_eval_count`/`eval_count`; Cerebras' `usage`),
  under its phase (`progress.current_activity()`, the ledger's name), engine and model; a
  stream left before its end is a call of no tokens. Meters nest. A build's worker measures
  its own and sends the summary with `worker.result` (`build_process` cleans it and adds it to
  the job's). The job's result carries `usage` (only when it called a model), and
  `logs/<slug>/usage.jsonl` keeps one line per job that called one — kind, end, status and
  tokens by phase, failed and stopped jobs included, never a text or an author
  (`server/jobs/usage_log.py`). `system usage --workspace S [--days N]` sums it by kind and
  engine. Embeddings are not counted.

## Closed decisions

One line per rule in force; the date, commit and reason of each are in
the root `DECISIONS.md`. Do not reverse one without the user's explicit request.

- D-075, D-076, D-077 — Queue per backend lane; local capacity 1 forever; remote capacity safe
  only with the ledger's claims. Three classes inside a lane, with aging, and a cap of
  background jobs on the local lane that aging does not lift.
- D-079 — `inference.generate()` streams internally and is interruptible; the stream is closed
  on abandon; waits are sliced.
- D-080, D-081 — The idle unload clock counts every lane; no shorter keep-alive instead.
- D-121, D-122 — A private job's events and routes are its author's (`PRIVATE_KINDS`); a
  build's are the subject's. A student's job says nothing of the bank.
