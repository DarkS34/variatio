# AGENTS.md — `consumers/` — the functions

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Each function has its own `AGENTS.md`: `generation/`, `evaluation/`, `tutor/`, `chat/`. What
the tutor and the chat share is `server/conversations/AGENTS.md`.

## `consumers/` — the functions the system is used through

Since 2026-10-14 (the user's request: the functions grouped in one directory) every door of
«Fase de pruebas» is a package of `consumers/`, an application in Django's sense: its routes, its
jobs, its settings, its prompts and an `install(app)` in its `api` package that
`server/app.py` calls, and nothing else does. The directory was `apps/` until 2026-10-16, when
the user asked for a name that says what these functions do: the construction produces the
artifacts and they consume them (`exploitation` was set aside, a word of abuse and of security
in English). **`consumers` imports `variatio` and `server`; neither
imports `consumers` back** but for the settings registry's optional imports and the four reads of
the evaluation older than the move (`jobs/lanes`, `pipeline/jobs`, `raw/documents`,
`admin/accounts`), each named in the import contracts of `pyproject.toml`
(`uv run lint-imports`); `tests/consumers/test_consumers_boundary.py` pins that a
function's library half imports neither FastAPI nor SQLAlchemy. On-disk names, setting keys,
job kinds and log scopes did not move with the code (`<workspace>/tutor/`, `tutor.*`,
`evaluation.*`, `tutor_turn`, `[tutor]`). The client mirrors it: `web/src/consumers/<function>/`.
Tests live in `tests/consumers/<function>/`.
