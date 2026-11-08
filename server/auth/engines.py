"""Which inference engine each account runs on, and the engine a request runs with.

An account names its engine in `users.inference_engine`; NULL is the installation's default,
`engine.name`. The engines an administrator may assign are the default plus
`engine.available`. The process holds an instance of every engine some active account runs
on and of no other (`sync`, over `core/process.py`'s `EngineSet`); a running job holds its
own until it ends, even when its account was moved to another engine meanwhile.

A request fixes its person's engine DEFERRED (`EngineContext`): the session is read only if
a route asks the engine or an engine-scoped setting, so a request that never does costs
nothing more.
"""

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from variatio import config, inference
from variatio.inference.engines import ENGINE_NAMES
from variatio.inference.interface import Engine

from ..core import process
from ..db import session_scope
from ..db.models import User
from . import queries
from .deps import session_token
from .tokens import digest


def offered() -> list[str]:
    """The engines an account may be given: the default first, then `engine.available`."""
    default = str(config.INFERENCE_ENGINE)
    extra = [str(name) for name in config.ENGINES_AVAILABLE]
    return [default, *(name for name in dict.fromkeys(extra) if name in ENGINE_NAMES and name != default)]


def name_for(user: User) -> str:
    """The engine `user` runs on: theirs when it is still offered, else the default."""
    own = user.inference_engine
    return own if own and own in offered() else str(config.INFERENCE_ENGINE)


def for_user(user: User) -> Engine:
    """The instance of the engine `user` runs on, built if it does not exist yet."""
    return process.engines.get(name_for(user))


def accounts_per_engine(db: DbSession) -> dict[str, int]:
    """How many active accounts run on each engine; an engine nobody runs on is absent."""
    counts: dict[str, int] = {}
    for user in db.scalars(select(User).where(User.disabled_at.is_(None))):
        name = name_for(user)
        counts[name] = counts.get(name, 0) + 1
    return counts


def sync() -> None:
    """Keep an instance of every engine some active account runs on, and of no other."""
    with session_scope() as db:
        wanted = set(accounts_per_engine(db))
    process.engines.keep(wanted)
    logger.info(f"[motores] Motores con cuentas: {', '.join(sorted(wanted)) or 'ninguno'}")


def assign(db: DbSession, user: User, engine: str | None) -> None:
    """Put `user` on `engine`, or back on the default with None; the caller checks `offered`."""
    user.inference_engine = engine
    db.commit()


def _engine_for_token(token: str | None) -> Engine:
    """The engine of the account behind a session cookie; the default without one.

    A read only: the session's sliding expiry is `deps.resolve`'s, on the route's own path.
    """
    name = str(config.INFERENCE_ENGINE)
    if token:
        with session_scope() as db:
            found = queries.live_session(db, digest(token))
            if found is not None:
                name = name_for(found[1])
    return process.engines.get(name)


class EngineContext:
    """Fix each HTTP request's engine: its person's, resolved only if something asks for it.

    Plain ASGI rather than `BaseHTTPMiddleware`: the context set here is the request task's,
    and AnyIO copies it into the worker thread of a sync route, which is where the deferred
    read happens when it happens.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap `app`."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run the request with its person's engine fixed, deferred."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = session_token(Request(scope))
        with inference.using_deferred(lambda: _engine_for_token(token)):
            await self.app(scope, receive, send)
