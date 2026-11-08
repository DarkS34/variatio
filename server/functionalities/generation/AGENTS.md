# AGENTS.md — `server/functionalities/generation/` — «Generar ejercicios»

Read the root `AGENTS.md` first.
The client is `web/src/consumers/generation/` (rules in `web/AGENTS.md`).

## A commission's bounds

- **A commission's bounds** (`server/functionalities/generation/limits.admit`, which `POST /api/jobs` hands
  a `generate` through `catalogue.ADMISSIONS`, under one lock with the queueing): one
  live `generate` per account and subject (409 `generation_busy`, every role); a student's
  count at most `GENERATION_STUDENT_MAX_ITEMS` (5, never above `GENERATION_MAX_ITEMS`; 422)
  and the day's exercises at most `GENERATION_STUDENT_DAILY_ITEMS` (empty = none) across
  every subject, counted as asked at queueing in `generation_usage` (`limits`' `usage`,
  migration 0018; a batch
  cancelled or failed gives nothing back): nothing left is 429 `generation_daily_limit` with
  `Retry-After`, some left is 422 naming how many. A teacher has neither bound.
  `GET /api/jobs/allowance` tells the form (`max_items`, `daily_items`, `used_today`); its
  stepper stops there and says what is left of the day, and `lib/limit.ts` words the 429 from
  its code and `Retry-After` (the wait's words are shared with the tutor's, `server/core/daily.py`
  on the server).
## `server/functionalities/generation/` — «Generar ejercicios»

Generating is no optional function and is always installed, FIRST: its
`GET /api/jobs/allowance` must be matched before the queue's `/api/jobs/{job_id}`. It holds
the author's routes (`/api/generations`, `router.py`), the `generate` job (`jobs.py`,
registered in `HANDLERS`) and a commission's bounds (`limits.py` and the day's count,
`usage.py`, registered in `catalogue.ADMISSIONS`). The generator is the library's (`variatio/functionalities/generation/`) and
the exercise files are the server's (`server/functionalities/shared/generations.py`, with `row_view`, read by the
panel, the activity and the tutor too). Its client is `web/src/consumers/generation/` (the form,
the run, «Mis ejercicios»), loaded like any screen: every account generates.
