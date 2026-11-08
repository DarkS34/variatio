"""«Generar ejercicios»: the commission, as the server takes it, runs it and keeps it.

The generator itself is the library's (`variatio/functionalities/generation/`, reached through
`variatio.api.generate`), and the files of the exercises are shared
(`server/functionalities/shared/generations.py`), read by the administrator's panel, the
class's activity and the tutor too. What is this function's alone is here: the author's routes,
the job that runs a commission, and the bounds a commission is admitted under. Mounted by the
composition root and nowhere else.

Generating is no optional function: there is no mode for it and it is always installed. It
is installed FIRST, before the core's routers (`server/app.py`), because its
`GET /api/jobs/allowance` has to be matched before the queue's `/api/jobs/{job_id}`.
"""


def install(app) -> None:
    """Register the `generate` handler and its admission, and mount the author's routes."""
    from server.jobs.catalogue import ADMISSIONS, HANDLERS

    from . import jobs, limits, router

    HANDLERS[jobs.GENERATE] = jobs.handle_generate
    ADMISSIONS[jobs.GENERATE] = limits.admit
    app.include_router(limits.router)
    app.include_router(router.router)
