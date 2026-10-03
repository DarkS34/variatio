"""What a teacher answered about each artifact: the key, the curation mark, the wording."""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import approvals
from server.db import Base, repository
from server.db.models import StageEvaluation
from evaluation.api import stage_instruments as instruments
from evaluation.api import stage_queries as queries
from evaluation.api import stages

GRAPH = approvals.KNOWLEDGE_GRAPH


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
        answers={"effort": 4},
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
    """"It came out wrong" and "I rebuilt it and it came out fine" are two data, not an edit of one."""
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
    _save(db, ws, "aaa", 3, artifact=approvals.EXEMPLARS_PROFILE)
    _save(db, ws, "aaa", 4, artifact=GRAPH)
    db.commit()
    assert len(db.query(StageEvaluation).all()) == 2


# OPENING -------------------------------------------------------------------------------


def test_opening_twice_does_not_move_the_stamp(db, ws):
    """A reload does not restart the clock: the same rule the study's own `opened_at` has."""
    first = queries.mark_opened(db, ws.id, 1, GRAPH, "aaa").opened_at
    again = queries.mark_opened(db, ws.id, 1, GRAPH, "aaa").opened_at
    assert first == again


def test_an_opened_form_is_a_row_before_it_is_answered(db, ws):
    """"Opened it and never answered" is a datum, and `overall is None` is what says so."""
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
# Correcting is not required in order to move on, so it becomes a VARIABLE: how somebody who
# corrected the artifact rates it against somebody who left it as it came out. The scale is
# "nobody said" < "no" < "yes", and a save may only ever climb it.


def test_a_verdict_that_says_nothing_does_not_know_whether_they_curated(db, ws):
    """Absence is "not known", which is not the same as "did not correct"."""
    row = _save(db, ws, "aaa", 4)
    db.commit()
    assert row.curated is None


def test_the_mark_arrives_with_the_answers(db, ws):
    assert _save(db, ws, "aaa", 4, curated=True).curated is True
    assert _save(db, ws, "bbb", 4, curated=False).curated is False


def test_curating_never_unsays_itself_on_the_same_build(db, ws):
    """Whoever corrected, corrected: re-answering the same build may not lower the mark.

    The real case is answering after correcting and then touching up the note from a screen
    that no longer knows an edit happened. Without the ratchet, that second save moves the
    row to the other side of the contrast.
    """
    _save(db, ws, "aaa", 4, curated=True)
    assert _save(db, ws, "aaa", 5, curated=False).curated is True
    assert _save(db, ws, "aaa", 3).curated is True
    db.commit()
    assert db.query(StageEvaluation).one().curated is True


def test_a_no_survives_a_later_silence(db, ws):
    """Un "no" tampoco se pierde: la ausencia no borra nada, ni hacia arriba ni hacia abajo."""
    _save(db, ws, "aaa", 4, curated=False)
    assert _save(db, ws, "aaa", 2).curated is False


def test_the_first_no_is_recorded_over_a_silence(db, ws):
    """What was unknown was only unknown the first time; saying it later does write."""
    _save(db, ws, "aaa", 4)
    assert _save(db, ws, "aaa", 4, curated=False).curated is False


def test_a_rebuild_starts_without_a_mark(db, ws):
    """Another build is another row, and nobody has yet corrected what has just come out."""
    _save(db, ws, "aaa", 4, curated=True)
    _save(db, ws, "bbb", 4)
    db.commit()
    rows = {r.artifact_hash: r.curated for r in db.query(StageEvaluation).all()}
    assert rows == {"aaa": True, "bbb": None}


def test_the_mark_is_this_persons_own(db, ws):
    """It is a variable of the EVALUATOR and not of the artifact: two accounts, two answers."""
    _save(db, ws, "aaa", 4, user=1, curated=True)
    _save(db, ws, "aaa", 4, user=2, curated=False)
    db.commit()
    assert queries.mine(db, ws.id, 1, GRAPH, "aaa").curated is True
    assert queries.mine(db, ws.id, 2, GRAPH, "aaa").curated is False


# WHAT THE FORM SENDS AND READS BACK ----------------------------------------------------


def test_a_request_that_omits_the_mark_is_perfectly_valid():
    """The client may not send it, and then it asserts nothing."""
    assert stages.AnswersBody().curated is None
    assert stages.AnswersBody(**{"overall": 4}).curated is None
    assert stages.AnswersBody(**{"curated": True}).curated is True


def test_the_form_reads_the_mark_back(db, ws):
    """It travels inside `mine`, which is what the form receives as its own state."""
    row = _save(db, ws, "aaa", 4, curated=True)
    db.commit()
    assert stages._mine(row)["curated"] is True
    assert stages._payload(GRAPH, "aaa", row)["mine"]["curated"] is True
    assert stages._mine(_save(db, ws, "bbb", 4))["curated"] is None


def test_the_route_carries_the_mark_from_the_body_to_the_row(db, ws, monkeypatch):
    """The PUT hands it to `save` and answers with it: that is the state the client keeps."""
    monkeypatch.setattr(stages, "_digest", lambda access, artifact: "aaa")
    access = SimpleNamespace(ws=None, workspace=ws, user=SimpleNamespace(id=1))

    saved = stages.write(GRAPH, stages.AnswersBody(overall=4, curated=True), access, db)
    assert saved["mine"]["curated"] is True

    # And a later silent re-answer does not clear it by the long route either.
    again = stages.write(GRAPH, stages.AnswersBody(overall=5), access, db)
    assert again["mine"]["curated"] is True
    db.commit()
    assert db.query(StageEvaluation).one().curated is True


# THE WORDING ---------------------------------------------------------------------------


def test_every_artifact_of_the_chain_has_questions():
    for artifact in approvals.ARTIFACTS:
        assert instruments.QUESTIONS.get(artifact), artifact
        assert instruments.PREAMBLE.get(artifact), artifact


def test_the_count_is_the_instruments_own_and_includes_overall():
    """The button that opens the form says how many questions there are, and is sent the count.

    A number written into the string contradicts the form it opens as soon as one instrument
    changes. `overall` counts: it is on the form, it is answered last, and it is what
    "answered" means.
    """
    for artifact in approvals.ARTIFACTS:
        expected = len(instruments.QUESTIONS[artifact]) + 1
        assert instruments.count(artifact) == expected, artifact
        assert instruments.for_artifact(artifact)["count"] == expected, artifact


def test_the_three_stages_ask_five_statements_on_the_same_axes():
    """Five per stage, on the same five axes, as statements over ONE shared Likert scale.

    Few enough not to overload, and each with a conclusion behind it: precision, recall, the
    artifact's own function, the effort and the overall. The same order and the SAME KEYS on
    all three, which is what lets them go side by side in a table with nothing translated.
    """
    for artifact in approvals.ARTIFACTS:
        assert instruments.count(artifact) == 5, artifact
        keys = [q["key"] for q in instruments.QUESTIONS[artifact]]
        assert keys == ["precision", "recall", "function", "effort"], artifact
        assert [instruments.AXES[k] for k in keys] == keys
        assert [q["axis"] for q in instruments.QUESTIONS[artifact]] == keys


def test_the_preamble_says_the_number_the_instrument_actually_asks():
    """The figure in the prose comes from `count()`, so adding a question cannot strand it."""
    for artifact in approvals.ARTIFACTS:
        spelled = instruments._SPELLED[instruments.count(artifact)]
        assert instruments.preamble(artifact).startswith(spelled + " afirmaciones"), artifact


def test_one_scale_for_every_statement_and_for_overall():
    """One five-rung scale, with its labels, shared by the whole form."""
    assert instruments.SCALE_VALUES == (1, 2, 3, 4, 5)
    assert len(instruments.SCALE_LABELS) == 5
    assert instruments.SCALE_LABELS[0].lower().startswith("totalmente en desacuerdo")
    assert instruments.SCALE_LABELS[-1].lower().startswith("totalmente de acuerdo")
    assert instruments.SCALE_MIN <= instruments.AGREE_FROM <= instruments.SCALE_MAX
    for artifact in approvals.ARTIFACTS:
        payload = instruments.for_artifact(artifact)
        assert payload["scale"] == {"min": 1, "max": 5, "labels": list(instruments.SCALE_LABELS)}
        assert payload["overall"]["statement"]
        for question in payload["questions"]:
            assert instruments.scale_values(artifact, question["key"]) == instruments.SCALE_VALUES


def test_the_two_comparable_items_are_asked_of_all_three():
    """`effort` and the overall are what the memoria can put in a table."""
    for artifact in approvals.ARTIFACTS:
        keys = [q["key"] for q in instruments.QUESTIONS[artifact]]
        assert "effort" in keys, artifact
        assert instruments.for_artifact(artifact)["overall"]["key"] == "overall"


def test_effort_is_worded_identically_everywhere():
    """Comparing across stages needs the statement to be THE SAME one, not a similar one."""
    asked = {
        next(q["statement"] for q in instruments.QUESTIONS[a] if q["key"] == "effort")
        for a in approvals.ARTIFACTS
    }
    assert len(asked) == 1


def test_no_question_key_repeats_within_an_artifact():
    for artifact in approvals.ARTIFACTS:
        keys = [q["key"] for q in instruments.QUESTIONS[artifact]]
        assert len(keys) == len(set(keys)), artifact


def test_every_statement_is_a_sentence_and_carries_no_options_of_its_own():
    """A Likert statement carries no options of its own: the scale is one and sits apart."""
    for artifact in approvals.ARTIFACTS:
        for question in instruments.QUESTIONS[artifact]:
            assert question["statement"].strip().endswith("."), (artifact, question["key"])
            assert "options" not in question, (artifact, question["key"])


def test_no_question_names_an_artefact_or_a_model():
    """The vocabulary is the teacher's: no statement names a piece of the system."""
    forbidden = ("grafo", "perfil de ejemplares", "banco de ejemplares", "artefacto", "modelo",
                 "workspace", "etiquetabilidad", "corpus", "prompt")
    for artifact in approvals.ARTIFACTS:
        payload = instruments.for_artifact(artifact)
        text = " ".join(
            [payload["preamble"], payload["overall"]["statement"]]
            + [q["statement"] + " " + q.get("hint", "") for q in payload["questions"]]
            + payload["scale"]["labels"]
        ).lower()
        for word in forbidden:
            assert word not in text, (artifact, word)


# WHAT ARRIVES IN A REQUEST -------------------------------------------------------------


def test_an_invented_answer_is_dropped_and_the_good_ones_survive():
    kept = instruments.clean(
        GRAPH, {"function": 5, "effort": "4", "inventada": 3, "foreign": "imposible"}
    )
    assert kept == {"function": 5, "effort": 4}


def test_a_value_off_the_scale_does_not_travel():
    """0, 6, a boolean or a word are not a rung, even where the key exists."""
    assert instruments.clean(GRAPH, {"precision": 0, "recall": 6}) == {}
    assert instruments.clean(GRAPH, {"precision": True, "recall": "muchos"}) == {}
    assert instruments.clean(GRAPH, {"precision": "none"}) == {}
    assert instruments.as_score("3") == 3 and instruments.as_score(2.0) is None


def test_scale_values_for_an_unknown_question_is_empty():
    assert instruments.scale_values(GRAPH, "no_existe") == ()
    assert instruments.scale_values("no_existe", "effort") == ()


def test_everything_carries_the_author_and_narrows_to_a_workspace(db, ws):
    from evaluation.api import stage_store

    other = repository.ensure_workspace(db, "other")
    db.commit()
    _save(db, ws, "h1", 4)
    _save(db, other, "h2", 2)

    rows = queries.everything(db)
    assert len(rows) == 2
    assert {workspace.slug for _, workspace, _ in rows} == {"default", "other"}

    only = stage_store.headers(db, ws.id)
    assert [h["workspace"] for h in only] == ["default"]
    assert only[0]["overall"] == 4 and only[0]["answered"] is True


def test_deleting_the_account_takes_its_forms_with_it():
    # SQLite enforces nothing unless told to, and this is exactly a test of enforcement.
    from sqlalchemy import event

    from server.db import identity
    from server.db.models import User

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    event.listen(engine, "connect", lambda con, _: con.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    ws = repository.ensure_workspace(db, "default")
    keeper = User(id=1, username="ana", name="ana", password_hash="x")
    leaver = User(id=2, username="bea", name="bea", password_hash="x")
    db.add_all([keeper, leaver])
    db.flush()
    _save(db, ws, "h", 4, user=1)
    _save(db, ws, "h", 2, user=2)
    db.commit()

    identity.delete_user(db, leaver)
    db.commit()

    rows = db.query(StageEvaluation).all()
    assert [(r.user_id, r.overall) for r in rows] == [(1, 4)]
