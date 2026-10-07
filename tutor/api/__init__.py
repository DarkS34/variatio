"""The tutor's server side, mounted by the composition root and nowhere else.

`server/app.py` is the one module of the installation that knows both halves, so it is where
the tutor is attached, as the evaluation was: importing it from `server/routers/__init__.py`
would close a cycle, since these routers import `server.auth` back.

Nothing here is imported until `install` runs, and `tutor/__init__.py` never reaches this
package: that is what keeps `import tutor` free of FastAPI and SQLAlchemy.
"""


def install(app) -> None:
    """Register the tutor's two jobs, their lanes and their function, and mount its routers."""
    from server import features
    from server.jobs import lanes
    from server.jobs.catalogue import PRIVATE_KINDS
    from server.jobs.handlers import HANDLERS
    from server.routers.jobs import FEATURE_OF
    from variatio import config as pipeline_config

    from .. import config as tutor_config
    from . import admin, jobs, router

    # Handlers only, and no entry in `JOB_LABELS`: that table is what `POST /api/jobs` accepts,
    # and a turn or a drafting must come through the tutor's own routes, which check what the
    # queue does not (the author's conversation, the construction closed, one reply at a time).
    # The screens name both kinds from their own catalogue (`lib/names.ts`).
    HANDLERS[jobs.TURN] = jobs.handle_turn
    HANDLERS[jobs.CRITERIA] = jobs.handle_criteria
    # Both are the tutor's: a lane they hold is named only to an account the tutor is open to.
    FEATURE_OF[jobs.TURN] = features.TUTOR
    FEATURE_OF[jobs.CRITERIA] = features.TUTOR
    # A turn is its author's alone, as a commission is: its events reach the author's socket
    # and nobody else's. The criteria are the subject's, and every teacher watches them.
    PRIVATE_KINDS.add(jobs.TURN)

    # The models each job calls, read at queueing time like every other kind's: the reply and
    # the classification for a turn, the drafting for the criteria, and — for both — what
    # warming a cold context may call (the concept describer and the repair).
    def warming() -> list[str]:
        """Return the models a cold context may call while it warms."""
        return [pipeline_config.DESCRIPTION_GENERATION_LLM, pipeline_config.REPAIR_LLM]

    lanes.EXTRA_MODELS[jobs.TURN] = lambda params: [
        tutor_config.REPLY_MODEL,
        tutor_config.CLASSIFY_MODEL,
        *warming(),
    ]
    lanes.EXTRA_MODELS[jobs.CRITERIA] = lambda params: [tutor_config.CRITERIA_MODEL, *warming()]

    app.include_router(router.router)
    app.include_router(admin.router)
