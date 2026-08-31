"""What a teacher answered about each artifact: the table's key, and the wording's shape."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import review
from server.db import Base, repository
from server.db.models import StageEvaluation
from study.api import stage_instruments as instruments
from study.api import stage_queries as queries

GRAPH = review.KNOWLEDGE_GRAPH


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def ws(db):
    workspace = repository.ensure_workspace(db, "default")
    db.commit()
    return workspace


def _save(db, ws, digest: str, overall: int, artifact: str = GRAPH, user: int | None = 1):
    return queries.save(
        db,
        ws.id,
        user,
        artifact,
        digest,
        instrument=instruments.VERSION,
        answers={"effort": "touch_up"},
        overall=overall,
        note=None,
    )


# THE KEY -------------------------------------------------------------------------------


def test_answering_the_same_build_twice_corrects_one_row(db, ws):
    _save(db, ws, "aaa", 3)
    _save(db, ws, "aaa", 5)
    db.commit()
    rows = db.query(StageEvaluation).all()
    assert len(rows) == 1
    assert rows[0].overall == 5


def test_a_rebuild_opens_a_second_row(db, ws):
    """«Salió mal» y «lo rehíce y salió bien» son dos datos, no una edición de uno."""
    _save(db, ws, "aaa", 2)
    _save(db, ws, "bbb", 5)
    db.commit()
    assert sorted(r.overall for r in db.query(StageEvaluation).all()) == [2, 5]


def test_two_people_judge_the_same_build_separately(db, ws):
    _save(db, ws, "aaa", 2, user=1)
    _save(db, ws, "aaa", 4, user=2)
    db.commit()
    assert len(db.query(StageEvaluation).all()) == 2


def test_each_artifact_is_its_own_row(db, ws):
    _save(db, ws, "aaa", 3, artifact=review.EXEMPLARS_PROFILE)
    _save(db, ws, "aaa", 4, artifact=GRAPH)
    db.commit()
    assert len(db.query(StageEvaluation).all()) == 2


# OPENING -------------------------------------------------------------------------------


def test_opening_twice_does_not_move_the_stamp(db, ws):
    """Una recarga no reinicia el cronómetro: es la misma regla que `opened_at` del estudio."""
    first = queries.mark_opened(db, ws.id, 1, GRAPH, "aaa").opened_at
    again = queries.mark_opened(db, ws.id, 1, GRAPH, "aaa").opened_at
    assert first == again


def test_an_opened_form_is_a_row_before_it_is_answered(db, ws):
    """«Lo abrió y no lo contestó» es un dato, y `overall is None` es lo que lo dice."""
    queries.mark_opened(db, ws.id, 1, GRAPH, "aaa")
    db.commit()
    row = db.query(StageEvaluation).one()
    assert row.opened_at is not None and row.overall is None
    assert queries.for_workspace(db, ws.id) == []
    assert len(queries.all_rows(db)) == 1


def test_saving_after_opening_keeps_the_same_row(db, ws):
    queries.mark_opened(db, ws.id, 1, GRAPH, "aaa")
    _save(db, ws, "aaa", 4)
    db.commit()
    row = db.query(StageEvaluation).one()
    assert row.opened_at is not None and row.overall == 4


# THE WORDING ---------------------------------------------------------------------------


def test_every_artifact_of_the_chain_has_questions():
    for artifact in review.ARTIFACTS:
        assert instruments.QUESTIONS.get(artifact), artifact
        assert instruments.PREAMBLE.get(artifact), artifact


def test_the_two_comparable_items_are_asked_of_all_three():
    """`effort` y la escala de conjunto son lo que la memoria puede poner en una tabla."""
    for artifact in review.ARTIFACTS:
        keys = [q["key"] for q in instruments.QUESTIONS[artifact]]
        assert "effort" in keys, artifact
        assert instruments.for_artifact(artifact)["overall"]["scale"]["max"] == 5


def test_effort_is_worded_identically_everywhere():
    """Comparar entre etapas exige que la pregunta sea LA MISMA, no una parecida."""
    asked = {
        next(q["question"] for q in instruments.QUESTIONS[a] if q["key"] == "effort")
        for a in review.ARTIFACTS
    }
    assert len(asked) == 1
    assert {
        tuple(instruments.options_for(a, "effort")) for a in review.ARTIFACTS
    } == {instruments.EFFORT_VALUES}


def test_no_question_key_repeats_within_an_artifact():
    for artifact in review.ARTIFACTS:
        keys = [q["key"] for q in instruments.QUESTIONS[artifact]]
        assert len(keys) == len(set(keys)), artifact


def test_every_question_offers_at_least_two_options():
    for artifact in review.ARTIFACTS:
        for question in instruments.QUESTIONS[artifact]:
            options = question.get("options") or []
            assert len(options) >= 2, (artifact, question["key"])
            values = [o["value"] for o in options]
            assert len(values) == len(set(values)), (artifact, question["key"])
            assert all(o.get("label") for o in options), (artifact, question["key"])


def test_no_question_names_an_artefact_or_a_model():
    """El vocabulario es el del profesor: ninguna pregunta nombra una pieza del sistema."""
    forbidden = ("grafo", "perfil de ejemplares", "banco de ejemplares", "artefacto", "modelo",
                 "workspace", "etiquetabilidad", "corpus", "prompt")
    for artifact in review.ARTIFACTS:
        payload = instruments.for_artifact(artifact)
        text = " ".join(
            [payload["preamble"]]
            + [q["question"] + " " + q.get("hint", "") for q in payload["questions"]]
            + [o["label"] for q in payload["questions"] for o in q.get("options", ())]
        ).lower()
        for word in forbidden:
            assert word not in text, (artifact, word)


# WHAT ARRIVES IN A REQUEST -------------------------------------------------------------


def test_an_invented_answer_is_dropped_and_the_good_ones_survive():
    kept = instruments.clean(
        GRAPH, {"order": "yes", "effort": "touch_up", "inventada": "x", "foreign": "imposible"}
    )
    assert kept == {"order": "yes", "effort": "touch_up"}


def test_a_question_of_another_artifact_does_not_travel():
    assert instruments.clean(GRAPH, {"tagging": "mostly"}) == {}


def test_options_for_an_unknown_question_is_empty():
    assert instruments.options_for(GRAPH, "no_existe") == ()
    assert instruments.options_for("no_existe", "effort") == ()
