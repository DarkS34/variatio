"""The order the server's own routers are mounted in, which is part of the routing.

FastAPI matches routes in declaration order, so the order here decides which route answers:
`admin`, `admin_engine` and `config` all sit under `/api/admin`, and a fixed path must stay
above any wildcard that could swallow it. `server/app.py` includes `ROUTERS` in this order,
after the generation's routes (its `/api/jobs/allowance` must come before the queue's
`/api/jobs/{job_id}`) and before the other functions'. Nothing else imports a route module.
"""

from .auth import router as auth
from .core.routes import health, maintenance, stream
from .jobs import router as jobs
from .pipeline.routes import context, pipeline
from .routers import (
    activity,
    admin,
    admin_engine,
    bank,
    config,
    exercises,
    kg,
    members,
    profile,
    raw,
)
from .workspaces import router as workspaces

ROUTERS = [
    auth.router,
    maintenance.router,
    workspaces.router,
    members.router,
    activity.router,
    health.router,
    pipeline.router,
    context.router,
    profile.router,
    kg.router,
    bank.router,
    exercises.router,
    raw.router,
    jobs.router,
    admin.router,
    admin_engine.router,
    config.router,
    stream.router,
]
