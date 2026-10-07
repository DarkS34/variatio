"""The engine and the session factory, both built on first use.

`import server` must keep working with no database reachable, exactly as importing
`variatio` works with no Ollama, so nothing here is created at import time.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_URL = "postgresql+psycopg://variatio:variatio@localhost:5432/variatio"

# Connections each process keeps, and how many more it may open on demand (2026-10-06, for a
# class of 100 at once; re-measure with a load test before trusting them further).
POOL_SIZE = 30
MAX_OVERFLOW = 30

_engine = None
_factory: sessionmaker | None = None


def get_session() -> Iterator[Session]:
    """Yield a session, as a FastAPI dependency."""
    with session_scope() as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a session that commits on the way out and rolls back on any exception."""
    session = factory()()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def factory() -> sessionmaker:
    """Return this process's session factory, creating it on first use."""
    global _factory
    if _factory is None:
        _factory = sessionmaker(bind=engine(), expire_on_commit=False, future=True)
    return _factory


def is_available() -> bool:
    """Return True when the database answers a connection attempt."""
    try:
        with engine().connect():
            return True
    except Exception:  # noqa: BLE001 - any connection failure is the same answer here
        return False


def engine():
    """Return this process's engine, creating it on first use."""
    global _engine
    if _engine is None:
        url = database_url()
        _engine = create_engine(url, pool_pre_ping=True, future=True, **_pool(url))
    return _engine


def _pool(url: str) -> dict[str, int]:
    """Return the connection pool's size, from `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW`.

    SQLAlchemy's default (5 kept, 10 more on demand) made a route wait for a connection with
    a class connected at once. Postgres must allow what every process sharing it may open:
    `max_connections` at least the sum of their pools. SQLite (the tests) keeps its own pool.
    """
    if url.startswith("sqlite"):
        return {}
    return {
        "pool_size": _positive("DATABASE_POOL_SIZE", POOL_SIZE),
        "max_overflow": _positive("DATABASE_MAX_OVERFLOW", MAX_OVERFLOW),
    }


def _positive(name: str, default: int) -> int:
    """Read a whole number from the environment, keeping the default on anything else."""
    try:
        value = int(os.environ.get(name, "") or default)
    except ValueError:
        return default
    return value if value >= 0 else default


def database_url() -> str:
    """Return `DATABASE_URL`, or the local Postgres this project ships with."""
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def reset() -> None:
    """Dispose of the engine and forget it, so the next call builds a new one."""
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _factory = None


def refusal(exc: Exception) -> str:
    """The one readable line inside a SQLAlchemy error, without the SQL and the params.

    `str()` of a `DBAPIError` carries the whole statement and every bound parameter, which
    for an artifact is hundreds of kilobytes of JSON in a single log line. What says what
    went wrong is the driver's own exception, and its first line is the sentence a person
    can act on.
    """
    original = getattr(exc, "orig", None) or exc
    return str(original).strip().splitlines()[0]
