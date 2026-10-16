"""The order the server's own routers are mounted in, which is part of the routing.

FastAPI matches routes in declaration order, so the order here decides which route answers:
the panel's nine modules (`admin/`) all sit under `/api/admin`, and a fixed path must stay
above any wildcard that could swallow it. `server/app.py` includes `ROUTERS` in this order,
after the generation's routes (its `/api/jobs/allowance` must come before the queue's
`/api/jobs/{job_id}`) and before the other functions'. Nothing else imports a route module.
"""

from .admin import accounts, class_links, features, invites, queue, settings
from .admin import engine as admin_engine
from .admin import maintenance as admin_maintenance
from .admin import workspaces as admin_workspaces
from .auth import router as auth
from .bank.routes import bank, exercises, profile
from .classroom.routes import activity, groups, links, people, uses
from .core.routes import health, maintenance, stream
from .jobs import router as jobs
from .kg import router as kg
from .pipeline.routes import context, pipeline
from .raw import router as raw
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
    # The panel, under `/api/admin`, one module per tab: a fixed path of one is never a
    # wildcard of another, and the queue's `/jobs` stays above the engine's `/jobs/history`.
    accounts.router,
    invites.router,
    class_links.router,
    admin_workspaces.router,
    queue.router,
    admin_maintenance.router,
    features.router,
    admin_engine.router,
    settings.router,
    stream.router,
]
