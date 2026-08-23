from . import (
    admin,
    admin_engine,
    auth,
    bank,
    config,
    context,
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
    admin.router,
    admin_engine.router,
    config.router,
    ws.router,
]

__all__ = ["ROUTERS"]
