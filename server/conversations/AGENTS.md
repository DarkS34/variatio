# AGENTS.md — `server/conversations/` — what the tutor and the chat share

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.

## `server/conversations/` — what the tutor and the chat share

Decided 2026-10-14 with the chat («nothing copied»); in `apps/conversations/` until 2026-10-16,
when the user moved it out: `consumers/` keeps the functions that work on the artifacts, and this
is no function (no route, job, setting or `install`). `store.Store` keeps one function's
conversations under `<workspace>/<folder>/user_<id>/<id>.json` (folder, reply role, initial
state and log scope are the function's), one lock per file, `pending` naming the job.
`usage.Limit` counts an account's turns per UTC day and function in `tutor_usage` (migration
0023 added `feature`; the rows before it are the tutor's; the unique key is account, day and
function). `jobs.QuietEmitter` lets only a turn's steps reach the stream and `jobs.release`
frees a conversation whose job died. `routes.Function` describes a function for the shared
route half — `require` (one's own or the same 404), `admit` (one reply per account in the
workspace, then the day's limit, 429 with the function's code and `Retry-After`),
`queue_turn`, `heal`, `detail`, `row`, `checked_message`, `require_engine`. It imports
`server` and the database, never `consumers`; only the two functions' `api` packages import it.
