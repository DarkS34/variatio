"""The commission's server side, mounted by the composition root and nowhere else.

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
