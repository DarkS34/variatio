"""The study's server side, mounted by the composition root and nowhere else.

`server/app.py` is the one module of the installation that knows both halves, so it is
where the study is attached: importing it from `routers/__init__.py` instead would close
a cycle, since these routers import `server.auth` and `server.routers.jobs` back.

Nothing here is imported until `install` runs, and `study/__init__.py` never reaches this
package: that is what keeps `import study` free of FastAPI and SQLAlchemy for a
runtime-only consumer, and `tests/study/test_study_boundary.py` pins it.
"""


def install(app) -> None:
    """Register the `evaluate` handler and mount the study's three routers on the app."""
    from server.jobs.handlers import HANDLERS

    from . import admin, jobs, router, stages

    HANDLERS["evaluate"] = jobs.handle_evaluate
    app.include_router(router.router)
    app.include_router(admin.router)
    # What a teacher answered about each artifact of the chain. A stage screen draws it,
    # but what it collects is the study's, so it is mounted here with the rest.
    app.include_router(stages.router)
