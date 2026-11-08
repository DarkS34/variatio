# AGENTS.md — `server/functionalities/shared/conversations/` — what the tutor and the chat share

Read the root `AGENTS.md` first.

## `server/functionalities/shared/conversations/` — what the tutor and the chat share

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
`server` and the database, never `consumers`; the two functions' `api` packages import its
store, usage, jobs and routes. The chat's prompts and both turns import the blocks below.

**The blocks of a chat-like system prompt**, in the library since 2026-11-08:
`variatio/prompts/conversation.py` resolves them, `variatio/prompts/{es,en}/conversation.py`
hold them (plan-prompts F8, 2026-11-03; D-235). One
set per prompt language (`of`). `system_prompt(role, method, subject=, language=, code=)` joins
six blocks in a fixed order: the function's role, the subject's `prompt_block()`, the language,
the scope, the format and the function's way of helping. The language block says the reply is in
the subject's `language_of_instruction` (`instruction_code` reads the free-text fact) whatever
the student writes in; the scope refuses in one sentence what is not the subject, a request for
the instructions or another role, and what is dangerous, works a sensitive topic of the subject at
the course's level, and answers a student in distress with care and a referral to the teacher or
someone they trust (D-236: what the guardrail's «harm» covered before); the format says how long a reply is and
how formulas are written, and how code is when `has_code` finds code in the message, the history
or the exercise. The chat is built on it and won 33–13 against its earlier prompt on the gold
messages. The tutor writes the language into its own method and takes only `instruction_code`:
the blocks lost against its method three times (see `variatio/functionalities/tutor/AGENTS.md`).
