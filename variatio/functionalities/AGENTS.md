# AGENTS.md — `variatio/functionalities/` and `server/functionalities/` — the functions

Read the root `AGENTS.md` first.
Each function has its own `AGENTS.md`: `evaluation/`, `tutor/` and `chat/` here, and the
generation's in `server/functionalities/generation/AGENTS.md`. What the tutor and the chat share
is `server/functionalities/shared/conversations/AGENTS.md`.

## The functions the system is used through

Every door of «Fase de pruebas» — generating exercises, the evaluation, the Socratic tutor and
the free chat — is a function, an application in Django's sense, in two halves since 2026-11-08
(the user's request: the same folder name holds the same thing in `variatio/` and `server/`):

- the **library half**, `variatio/functionalities/<function>/`: what the function computes, its
  settings (`settings.py`, read through its `config.py`), and no FastAPI or SQLAlchemy; its
  prompts are `variatio/prompts/{es,en}/<function>.py`, resolved by `variatio/prompts/<function>.py`.
  The generation's library half is the generator and its checks.
- the **server half**, `server/functionalities/<function>/`: its routes, jobs, stores and
  counts, and an `install(app)` in its `__init__.py` that `server/app.py` calls, and nothing else
  does. The generation has no library-only module besides the generator.

**No function imports another**; what several use is `functionalities/shared/` on each side
(`screening/` in the library; `conversations/` and `generations.py` in the server). Each
exception is named in the import contracts of `pyproject.toml` (`uv run lint-imports`): the
settings registry's optional imports of each `settings.py`, and the evaluation, which runs the
whole system through `variatio.api` and reuses the generator.
`tests/functionalities/test_functions_boundary.py` pins that a function's library half imports neither
FastAPI nor SQLAlchemy. The functions were `apps/` until 2026-10-16 and `consumers/` until
2026-11-08. On-disk names, setting keys, job kinds and log scopes did not move with the code
(`<workspace>/tutor/`, `tutor.*`, `evaluation.*`, `tutor_turn`, `[tutor]`). The client keeps
`web/src/consumers/<function>/`. Tests live in `tests/functionalities/<function>/`.
