# AGENTS.md — `server/admin/` — «Administración»

Read the root `AGENTS.md` and `server/AGENTS.md` first. The closed decisions are numbered in
the root `DECISIONS.md`. The screen is `web/src/features/admin/AGENTS.md`; who an invitation
makes and how it is sealed is `server/auth/AGENTS.md`.

One route module per tab or section of the panel: `accounts.py` (the front page, `/overview`,
and an account's gestures and memberships), `invites.py`, `class_links.py`, `workspaces.py`,
`queue.py`, `maintenance.py`, `features.py`, `engine.py` and `settings.py`. What two of them
share is `shared.py`, since no route module imports another. The evaluation mounts its own tab
beside them (`consumers/evaluation/api/admin.py`).

- **Every route is behind `require_admin`, under `/api/admin`.** The nine routers are mounted
  one after the other (`server/routing.py`): a fixed path of one is never a wildcard of
  another, and the queue's `/jobs` stays above the engine's `/jobs/history`.
- **The panel is no second way into the pipeline**: nothing here builds, edits or approves.
  It reads what the installation recorded, hands out access and exports a CSV. It reads
  across accounts in two places only: the evaluation on the front page, and a subject's
  generated exercises, read-only (`GET /api/admin/workspaces/{slug}/generations`).
- Deleting a subject or an artifact is the panel's (D-114); when a deletion takes the tree is
  `workspaces/AGENTS.md`.
