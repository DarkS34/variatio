"""The order the server's own routers are mounted in, which is part of the routing.

FastAPI matches routes in declaration order, so the order here decides which route answers:
`admin`, `admin_engine` and `config` all sit under `/api/admin`, and a fixed path must stay
above any wildcard that could swallow it. `server/app.py` includes `ROUTERS` in this order,
after the generation's routes (its `/api/jobs/allowance` must come before the queue's
`/api/jobs/{job_id}`) and before the other functions'. Nothing else imports a route module.
"""

from .auth import router as auth
from .bank.routes import bank, exercises, profile
from .classroom.routes import activity, groups, links, people, uses
from .core.routes import health, maintenance, stream
from .jobs import router as jobs
from .kg import router as kg
from .pipeline.routes import context, pipeline
from .raw import router as raw
from .routers import admin, admin_engine, config
from .workspaces import router as workspaces

ROUTERS = [
    auth.router,
    maintenance.router,
    workspaces.router,
    # `/api/members` in four parts: no fixed path of one is a `{user_id:int}` of another.
    people.router,
    groups.router,
    uses.router,
    links.router,
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
