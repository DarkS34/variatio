import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.db import Base, repository
from study.api import queries


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def _seed(db, *ids: str) -> None:
    ws = repository.ensure_workspace(db, "default")
    for sid in ids:
        queries.upsert_evaluation(db, sid, ws.id, None, {"item_type": "t", "seed": 1})
    db.commit()


def test_deletes_only_the_named_sessions(db):
    _seed(db, "a", "b", "c")
    assert sorted(queries.delete_evaluations(db, ["a", "c"])) == ["a", "c"]
    db.commit()
    rows, total = queries.list_evaluations(db)
    assert total == 1 and rows[0].id == "b"


def test_unknown_ids_are_ignored(db):
    _seed(db, "a")
    assert queries.delete_evaluations(db, ["zzz"]) == []
    assert queries.delete_evaluations(db, []) == []
    assert queries.list_evaluations(db)[1] == 1
