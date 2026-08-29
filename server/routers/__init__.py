"""Every HTTP and WebSocket surface the API exposes.

`ROUTERS` is included into the app in this order and FastAPI matches routes in
declaration order, so the order here is part of the routing: `admin`, `admin_engine`
and `config` all sit under `/api/admin`, and a fixed path must stay above any wildcard
that could swallow it.
"""

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
    maintenance,
    pipeline,
    profile,
    raw,
    workspaces,
    ws,
)

ROUTERS = [
    auth.router,
    maintenance.router,
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
