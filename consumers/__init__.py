"""The functions the system is used through, one package each, beside the library they read.

Each is an application in Django's sense: its routes, its jobs, its settings and its prompts,
and an `install(app)` in its `api` package that the composition root (`server/app.py`) calls.
They are the doors of «Fase de pruebas»: generating exercises, the evaluation, the Socratic
tutor and the free chat. The name says what they have in common: the construction produces the
artifacts, and these consume them.

`consumers` imports `variatio` and `server`, and neither of them imports `consumers` back, but
for the settings registry's optional imports and the places
`tests/consumers/test_consumers_boundary.py` lists.
"""
