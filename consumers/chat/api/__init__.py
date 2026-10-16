"""The free chat's server side, mounted by the composition root and nowhere else.

Nothing here is imported until `install` runs, and `consumers/chat/__init__.py` never reaches this
package: that is what keeps `import consumers.chat` free of FastAPI and SQLAlchemy.
"""


def install(app) -> None:
    """Register the chat's turn, its lane and its function, and mount its router."""
    from server.auth import features
    from server.classroom import activity as class_activity
    from server.jobs import lanes
    from server.jobs.catalogue import (
        FEATURE_OF,
        HANDLERS,
        INTERACTIVE,
        JOB_CLASS,
        PRIVATE_KINDS,
        STUDENT_KINDS,
    )

    from .. import config as chat_config
    from . import activity, jobs, router

    # A handler and no entry in `JOB_LABELS`: a turn comes through the chat's own routes,
    # which check what the queue does not (the author's conversation, one reply at a time).
    HANDLERS[jobs.TURN] = jobs.handle_turn
    # A lane it holds is named only to an account the chat is open to.
    FEATURE_OF[jobs.TURN] = features.CHAT
    # Its author's alone, a student's to ask for, and the queue's first class: somebody waits
    # in a chat for it, as for the tutor's.
    PRIVATE_KINDS.add(jobs.TURN)
    STUDENT_KINDS.add(jobs.TURN)
    JOB_CLASS[jobs.TURN] = INTERACTIVE
    # The guardrail is no generative model and reserves no lane; the reply does.
    lanes.EXTRA_MODELS[jobs.TURN] = lambda params: [chat_config.REPLY_MODEL]
    # The teachers' weekly counts read the chat's conversations through this package.
    class_activity.CHAT_READER = activity.read

    app.include_router(router.router)
