import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_URL = "postgresql+psycopg://variatio:variatio@localhost:5432/variatio"

_engine = None
_factory: sessionmaker | None = None


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


# Created on first use, not at import: `import server` must keep working with no database
# reachable, exactly as importing `variatio` works with no Ollama.
def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(database_url(), pool_pre_ping=True, future=True)
    return _engine


def factory() -> sessionmaker:
    global _factory
    if _factory is None:
        _factory = sessionmaker(bind=engine(), expire_on_commit=False, future=True)
    return _factory


@contextmanager
def session_scope() -> Iterator[Session]:
    session = factory()()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    with session_scope() as session:
        yield session


def is_available() -> bool:
    try:
        with engine().connect():
            return True
    except Exception:  # noqa: BLE001 - any connection failure is the same answer here
        return False


def reset() -> None:
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _factory = None
