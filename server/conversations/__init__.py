"""What the conversational functions share: a store of conversations and a daily count.

The Socratic tutor and the free chat keep their conversations the same way — one JSON file per
conversation, under its author's directory, written whole under a lock per file, with
`pending` naming the job a reply is coming from — and count the turns an account queues each
day the same way. Both live here once (`store.Store`, `usage.Limit`), each function naming its
folder and its name (the user's decision, 2026-10-14: nothing copied).

Kept in `server/`, not in `consumers/`: it is no function of its own (no route, job, setting or
`install`), only what two functions' `api` packages share. It imports `server` and the
database, never `consumers`, and no library module imports it.
"""
