from . import (
    admin,
    auth,
    bank,
    context,
    evaluation,
    generations,
    health,
    jobs,
    kg,
    pipeline,
    profile,
    raw,
    workspaces,
    ws,
)

ROUTERS = [
    auth.router,
    workspaces.router,
    health.router,
    pipeline.router,
    context.router,
    profile.router,
    kg.router,
    bank.router,
    raw.router,
    jobs.router,
    generations.router,
    evaluation.router,
    admin.router,
    ws.router,
]

__all__ = ["ROUTERS"]
