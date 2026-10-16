# AGENTS.md — `server/core/` — what every area stands on

Read the root `AGENTS.md` and `server/AGENTS.md` first. The closed decisions are numbered in
the root `DECISIONS.md`; none is this folder's alone.

The pieces the server needs and that know no area: the process's live pieces (`process.py`),
the warm contexts (`contexts.py`), resolving a subject (`installation.py`), the environment
(`environment.py`), the SSH tunnel (`tunnel.py`), model downloads (`model_pulls.py`), the
maintenance door (`maintenance.py`), the origin check and the security headers
(`middleware.py`), days and weeks (`daily.py`) and CSV cells (`csv_safe.py`). `routes/` holds `/api/health`, `/api/maintenance` and the WebSocket
stream (`/ws`).

## Boundaries

- **The core imports no area.** In the server's layers (an import contract) `core/` sits
  above `jobs/` and `db/`, and below `conversations/`, `generations.py`, `auth/` and every
  area. Its routes are leaves: they may import any area, and only `server/routing.py`
  imports them.
- **One bus and one queue for the whole installation** (`process.py`, with the idle unloader,
  the tunnel and the downloads): the core assembles them from the queue's machinery in
  `jobs/`. The queue knows nothing about the chain; `server/app.py` wires it
  (`pipeline.chain.wire`). Code reads them as `process.runner`, never imported by name, so a
  test that puts its own runner there is the one everybody sees.
- **The API's switches and limits are `environment.py`**: production, cookies and sessions,
  the lifetimes and sizes of invitations and class links, mail, rate limits and the client's
  build. The database's variables are `db/session.py`'s, and the
  invitations' key `auth/links.py`'s. None of it is a setting (`variatio/settings/` is the
  settings registry).
- **Every path of a subject comes from its slug**, through `installation.workspace_for`;
  there is no no-argument `workspace()` (D-010).

## Warm contexts (`contexts.py`)

- An LRU (`MAX_CONTEXTS`, 8) of `RuntimeContext`s keyed by slug, touched only from the job
  worker. Each workspace has its own lock, held across `initialize` (2026-10-06: one lock for
  all made a subject warming up hold every other subject's jobs); `_lock` only guards the
  dicts. An invalidation during a build bumps the workspace's generation and that build's
  context is not kept. Runtime components keep no per-run state on `self` (two jobs of one
  workspace may share a context).
- A job gets its context through `context_for(job)`: a warm one is reused; a cold one warms
  in a step of its own, because it embeds every concept description and the whole bank. It
  reads only `job.workspace`, so this module imports nothing of the queue.

## Health, the tunnel and the downloads

- `GET /api/health` reads the engine once every `READ_EVERY` (5) seconds for the whole
  process, one thread at a time (`routes/health.engine_reading`): the others answer with the
  reading before, and only the first request ever waits. A class's hundred tabs poll it. The
  panel's «Motor» reads the engine live (`/api/admin/engine`).
- The API owns the SSH tunnel to the GPU box (`tunnel.py`, system `ssh -N -L`,
  `BatchMode=yes`, watchdog with backoff).
- A model download gets a thread of its own and never enters the queue (`model_pulls.py`):
  it is network and disk, not the GPU, and must not wait behind a build.

## The door

- The maintenance door is `/.maintenance.json` at the root (git-ignored), so a restart does
  not open it again. A closed door does not lock out the administrator: the check is in
  `auth.deps.access_for`, beside the administrator's bypass. `GET /api/maintenance` is the one
  route with no authorisation, because the entrance screen reads it before anybody logs in.
