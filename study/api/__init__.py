"""The study's server side, mounted by the composition root and nowhere else.

`server/app.py` is the one module of the installation that knows both halves, so it is
where the study is attached: importing it from `routers/__init__.py` instead would close
a cycle, since these routers import `server.auth` and `server.routers.jobs` back.

Nothing under `study/` is imported until `install` runs, which is what keeps `import
study` free of FastAPI and SQLAlchemy for a runtime-only consumer.
"""


def install(app) -> None:
    from server.jobs.handlers import HANDLERS

    from . import admin, jobs, router

    HANDLERS["evaluate"] = jobs.handle_evaluate
    app.include_router(router.router)
    app.include_router(admin.router)
