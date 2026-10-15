"""The functions the system is used through, one package each, beside the library they read.

Each is an application in Django's sense: its routes, its jobs, its settings and its prompts,
and an `install(app)` in its `api` package that the composition root (`server/app.py`) calls.
They are the doors of «Fase de pruebas»: generating exercises, the evaluation, the Socratic
tutor and the free chat.

`apps` imports `variatio` and `server`, and neither of them imports `apps` back, but for the
settings registry's optional imports and the places `tests/apps/test_apps_boundary.py` lists.
"""
