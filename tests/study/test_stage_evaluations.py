"""What a teacher answered about each artifact: the key, the curation mark, the wording."""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import review
from server.db import Base, repository
from server.db.models import StageEvaluation
from study.api import stage_instruments as instruments
from study.api import stage_queries as queries
from study.api import stages

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


def _save(
    db,
    ws,
    digest: str,
    overall: int,
    artifact: str = GRAPH,
    user: int | None = 1,
    curated: bool | None = None,
):
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
        curated=curated,
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


# CURATING, WHICH IS THE CONTRAST -------------------------------------------------------
#
# Curar dejó de hacer falta para avanzar, así que pasa a ser una variable: cómo valora
# quien corrigió el artefacto frente a cómo valora quien lo dejó tal cual salió. La escala
# es «nadie lo dijo» < «no» < «sí», y un guardado solo puede subir por ella.


def test_a_verdict_that_says_nothing_does_not_know_whether_they_curated(db, ws):
    """La ausencia es «no se sabe», que no es lo mismo que «no curó»."""
    row = _save(db, ws, "aaa", 4)
    db.commit()
    assert row.curated is None


def test_the_mark_arrives_with_the_answers(db, ws):
    assert _save(db, ws, "aaa", 4, curated=True).curated is True
    assert _save(db, ws, "bbb", 4, curated=False).curated is False


def test_curating_never_unsays_itself_on_the_same_build(db, ws):
    """Quien curó, curó: una re-respuesta sobre el mismo build no puede bajar la marca.

    Es el caso real: se contesta tras corregir, y más tarde se retoca la nota desde una
    pantalla que ya no sabe que hubo edición. Sin la trinquete, ese segundo guardado movería
    la fila al otro lado del contraste.
    """
    _save(db, ws, "aaa", 4, curated=True)
    assert _save(db, ws, "aaa", 5, curated=False).curated is True
    assert _save(db, ws, "aaa", 3).curated is True
    db.commit()
    assert db.query(StageEvaluation).one().curated is True


def test_a_no_survives_a_later_silence(db, ws):
    """Un «no» tampoco se pierde: la ausencia no borra nada, ni hacia arriba ni hacia abajo."""
    _save(db, ws, "aaa", 4, curated=False)
    assert _save(db, ws, "aaa", 2).curated is False


def test_the_first_no_is_recorded_over_a_silence(db, ws):
    """Lo único que no se sabía era la primera vez; decirlo después sí escribe."""
    _save(db, ws, "aaa", 4)
    assert _save(db, ws, "aaa", 4, curated=False).curated is False


def test_a_rebuild_starts_without_a_mark(db, ws):
    """Otro build es otra fila, y nadie ha curado todavía lo que acaba de salir."""
    _save(db, ws, "aaa", 4, curated=True)
    _save(db, ws, "bbb", 4)
    db.commit()
    rows = {r.artifact_hash: r.curated for r in db.query(StageEvaluation).all()}
    assert rows == {"aaa": True, "bbb": None}


def test_the_mark_is_this_persons_own(db, ws):
    """Es una variable del evaluador, no del artefacto: dos cuentas, dos respuestas."""
    _save(db, ws, "aaa", 4, user=1, curated=True)
    _save(db, ws, "aaa", 4, user=2, curated=False)
    db.commit()
    assert queries.mine(db, ws.id, 1, GRAPH, "aaa").curated is True
    assert queries.mine(db, ws.id, 2, GRAPH, "aaa").curated is False


# WHAT THE FORM SENDS AND READS BACK ----------------------------------------------------


def test_a_request_that_omits_the_mark_is_perfectly_valid():
    """El cliente puede no mandarla, y entonces no afirma nada."""
    assert stages.AnswersBody().curated is None
    assert stages.AnswersBody(**{"overall": 4}).curated is None
    assert stages.AnswersBody(**{"curated": True}).curated is True


def test_the_form_reads_the_mark_back(db, ws):
    """Va dentro de `mine`, que es lo que el formulario recibe como estado propio."""
    row = _save(db, ws, "aaa", 4, curated=True)
    db.commit()
    assert stages._mine(row)["curated"] is True
    assert stages._payload(GRAPH, "aaa", row)["mine"]["curated"] is True
    assert stages._mine(_save(db, ws, "bbb", 4))["curated"] is None


def test_the_route_carries_the_mark_from_the_body_to_the_row(db, ws, monkeypatch):
    """El PUT la pasa a `save`, y la contesta: es el estado con el que se queda el cliente."""
    monkeypatch.setattr(stages, "_digest", lambda access, artifact: "aaa")
    access = SimpleNamespace(ws=None, workspace=ws, user=SimpleNamespace(id=1))

    saved = stages.write(GRAPH, stages.AnswersBody(overall=4, curated=True), access, db)
    assert saved["mine"]["curated"] is True

    # Y la re-respuesta muda que llegue después tampoco la borra por el camino largo.
    again = stages.write(GRAPH, stages.AnswersBody(overall=5), access, db)
    assert again["mine"]["curated"] is True
    db.commit()
    assert db.query(StageEvaluation).one().curated is True


# THE WORDING ---------------------------------------------------------------------------


def test_every_artifact_of_the_chain_has_questions():
    for artifact in review.ARTIFACTS:
        assert instruments.QUESTIONS.get(artifact), artifact
        assert instruments.PREAMBLE.get(artifact), artifact


def test_the_count_is_the_instruments_own_and_includes_overall():
    """El botón que abre el formulario dice cuántas preguntas hay, y se le manda la cuenta.

    Decía «cinco» fijo en las tres etapas mientras el temario preguntaba seis, así que el
    control contradecía al formulario que abre. `overall` cuenta: está en el formulario, es
    lo último que se contesta y es lo que significa «contestada».
    """
    for artifact in review.ARTIFACTS:
        expected = len(instruments.QUESTIONS[artifact]) + 1
        assert instruments.count(artifact) == expected, artifact
        assert instruments.for_artifact(artifact)["count"] == expected, artifact


def test_the_three_stages_ask_five_questions_on_the_same_axes():
    """Cinco por etapa y los mismos cinco ejes (2026-09-03, explicit user request).

    Pocas para no sobrecargar, y cada una con una conclusión detrás: precisión, cobertura,
    la función propia del artefacto, el esfuerzo y la escala de conjunto. El mismo orden
    en las tres, que es lo que deja ponerlas en una tabla lado a lado.
    """
    for artifact in review.ARTIFACTS:
        assert instruments.count(artifact) == 5, artifact
        axes = [instruments.AXES[q["key"]] for q in instruments.QUESTIONS[artifact]]
        assert axes == ["precision", "recall", "function", "effort"], artifact


def test_the_preamble_says_the_number_the_instrument_actually_asks():
    """La cifra de la prosa sale de `count()`, así que no puede desfasarse al añadir una."""
    for artifact in review.ARTIFACTS:
        spelled = instruments._SPELLED[instruments.count(artifact)]
        assert instruments.preamble(artifact).startswith(spelled + " preguntas"), artifact


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
