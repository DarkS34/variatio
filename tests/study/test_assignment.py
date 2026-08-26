"""Handing the same three items to two people, and what each of them records.

The property under test is the one the whole overlap design rests on: the copies must
agree about the EXERCISES and disagree freely about everything else — order, timing,
triage, choice — because two evaluators who share a shuffle share a position bias, and an
agreement that includes it is not an agreement about the exercises at all.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.db.models import Base, User, Workspace
from study import EvaluationSession
from study.api import queries
from study.api import store as evaluation_store


def _arm(name, text):
    return {
        "arm": name,
        "status": "ok",
        "item": {"enunciado": text},
        "raw_response": "{}",
        "prompt": f"prompt de {name}",
        "model": "modelo",
        "provider": "local",
        "exemplar_ids": [],
        "elapsed_ms": 1200,
        "error": None,
        "checks": None,
        "retried": 0,
    }


SOURCE = {
    "id": "origen000001",
    "created_at": 1000.0,
    "job_id": "job1",
    "set_id": "origen000001",
    "assigned_by": None,
    "concepts": ["Recursividad"],
    "item_type": "escritura_codigo",
    "fixed": {},
    "curriculum": [],
    "instructions": "",
    "seed": 42,
    "shuffle": ["naive", "rag", "system"],
    "think": False,
    "arms": {
        "naive": _arm("naive", "el comercial"),
        "rag": _arm("rag", "el de similitud"),
        "system": _arm("system", "el del grafo"),
    },
    "triage": {"1": "yes", "2": "no", "3": "partly"},
    "choice": 3,
    "choice_arm": "system",
    "chosen_at": 1100.0,
    "opened_at": 1000.0,
    "declined_at": None,
    "evaluator_note": "la tercera",
    "rating": {"arm": "system", "soundness": 5},
}


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    workspace = Workspace(slug="asignatura", name="Asignatura")
    session.add(workspace)
    session.flush()
    for index, username in enumerate(("ana", "berta", "admin"), start=1):
        session.add(
            User(
                id=index,
                username=username,
                name=username,
                password_hash="x",
                evaluator_profile="teacher",
            )
        )
    session.flush()
    queries.upsert_evaluation(session, SOURCE["id"], workspace.id, 1, SOURCE)
    yield session
    session.close()


def _source(db):
    return queries.get_evaluation(db, SOURCE["id"])


# WHAT IS COPIED --------------------------------------------------------------------------


def test_the_copy_carries_the_very_same_three_items(db):
    copy = evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3)
    for arm in ("naive", "rag", "system"):
        assert copy.arms[arm].item == SOURCE["arms"][arm]["item"]


def test_the_copy_shares_the_set_but_not_the_identity(db):
    copy = evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3)
    assert copy.set_id == SOURCE["id"]
    assert copy.id != SOURCE["id"]


def test_the_copy_inherits_the_reasoning_condition_rather_than_drawing_a_new_one(db):
    # These three items were generated with reasoning off. Redrawing it on the copy would
    # record a lie about how they were made.
    copy = evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3)
    assert copy.think is False


def test_the_copy_says_who_handed_it_over(db):
    copy = evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3)
    assert copy.assigned_by == 3
    row = queries.get_evaluation(db, copy.id)
    assert row.user_id == 2


# WHAT IS NOT COPIED ----------------------------------------------------------------------


def test_the_copy_arrives_unjudged(db):
    copy = evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3)
    assert copy.triage == {}
    assert copy.choice is None
    assert copy.choice_arm is None
    assert copy.chosen_at is None
    assert copy.rating is None
    assert copy.evaluator_note is None
    assert copy.opened_at is None
    assert not copy.finished


def test_the_copy_gets_an_order_of_its_own(db):
    # Given a fixed seed the shuffle is deterministic, which is what makes «distinto orden»
    # something a test can assert rather than a hope about randomness.
    copy = evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3, seed=7)
    assert sorted(copy.shuffle) == sorted(SOURCE["shuffle"])
    assert copy.seed == 7
    other = evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3, seed=7, allow_repeat=True)
    assert other.shuffle == copy.shuffle


def test_a_position_means_different_arms_for_the_two_evaluators(db):
    # The point of the fresh shuffle: whatever «la propuesta A» is for one of them, it is
    # not necessarily the same architecture for the other.
    seeds = [evaluation_store.assign(db, _source(db), 2, 3, seed=s, allow_repeat=True) for s in range(20)]
    assert any(copy.shuffle != SOURCE["shuffle"] for copy in seeds)


# WHO GETS IT -----------------------------------------------------------------------------


def test_the_same_set_is_not_handed_to_the_same_person_twice_by_accident(db):
    evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3)
    with pytest.raises(ValueError, match="already-assigned"):
        evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3)


def test_a_repeat_is_allowed_when_it_is_asked_for(db):
    # Test-retest: the same person, the same three items, later. The only reliability an
    # evaluator alone in their subject can contribute.
    first = evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3)
    second = evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3, allow_repeat=True)
    assert first.id != second.id
    assert len(queries.sessions_in_set(db, SOURCE["id"])) == 3


def test_the_author_of_the_original_counts_as_already_having_it(db):
    with pytest.raises(ValueError, match="already-assigned"):
        evaluation_store.assign(db, _source(db), user_id=1, assigned_by=3)


# THE QUEUE -------------------------------------------------------------------------------


def test_the_queue_holds_what_was_assigned_and_not_what_was_self_commissioned(db):
    evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3)
    assert [row.user_id for row in queries.assigned_to(db, 1, 2)] == [2]
    # Ana commissioned the original herself, so nothing was handed to her.
    assert queries.assigned_to(db, 1, 1) == []


def test_a_finished_session_leaves_the_pending_queue(db):
    copy = evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3)
    assert len(queries.assigned_to(db, 1, 2, pending_only=True)) == 1

    evaluation_store.record_choice(db, queries.get_evaluation(db, copy.id), 1)
    assert queries.assigned_to(db, 1, 2, pending_only=True) == []
    assert len(queries.assigned_to(db, 1, 2)) == 1


def test_a_set_lists_once_however_many_people_hold_it(db):
    evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3)
    assert [row.id for row in queries.sets_in_workspace(db, 1)] == [SOURCE["id"]]


# TRIAGE AND DECLINE ----------------------------------------------------------------------


def _fresh(db):
    copy = evaluation_store.assign(db, _source(db), user_id=2, assigned_by=3)
    return queries.get_evaluation(db, copy.id)


def test_the_triage_is_recorded_by_position_and_read_back_by_arm(db):
    row = _fresh(db)
    session = evaluation_store.record_triage(db, row, 1, "yes")
    assert session.triage == {"1": "yes"}
    assert session.triage_by_arm() == {session.arm_at(1): "yes"}


def test_an_invented_triage_value_is_refused(db):
    with pytest.raises(ValueError, match="must be one of"):
        evaluation_store.record_triage(db, _fresh(db), 1, "quizás")


def test_the_triage_closes_with_the_session(db):
    row = _fresh(db)
    evaluation_store.record_choice(db, row, 2)
    with pytest.raises(ValueError, match="already-chosen"):
        evaluation_store.record_triage(db, queries.get_evaluation(db, row.id), 1, "yes")


def test_a_decline_ends_the_session_without_recording_a_preference(db):
    row = _fresh(db)
    session = evaluation_store.record_decline(db, row, "no doy esta asignatura")
    assert session.declined and session.finished
    assert not session.decided
    assert session.chosen_at is None
    assert session.choice_arm is None


def test_a_declined_session_still_reveals(db):
    session = evaluation_store.record_decline(db, _fresh(db))
    # Withholding the answer from somebody who just said they could not judge it would be
    # a punishment for having said so.
    assert session.finished


def test_a_session_is_judged_once(db):
    row = _fresh(db)
    evaluation_store.record_choice(db, row, 1)
    with pytest.raises(ValueError, match="already-chosen"):
        evaluation_store.record_decline(db, queries.get_evaluation(db, row.id))


# THE CLOCK -------------------------------------------------------------------------------


def test_opening_starts_the_clock(db):
    row = _fresh(db)
    evaluation_store.mark_opened(db, row)
    assert queries.get_evaluation(db, row.id).opened_at is not None


def test_a_reload_does_not_restart_the_clock(db):
    row = _fresh(db)
    evaluation_store.mark_opened(db, row)
    first = queries.get_evaluation(db, row.id).opened_at

    evaluation_store.mark_opened(db, queries.get_evaluation(db, row.id))
    assert queries.get_evaluation(db, row.id).opened_at == first


def test_the_header_reports_how_long_the_judgement_took(db):
    row = _fresh(db)
    session = EvaluationSession.from_dict(row.trace)
    session.opened_at = 500.0
    session.chosen_at = 545.5
    session.choice = 1
    queries.upsert_evaluation(db, session.id, 1, 2, session.to_dict())

    header = evaluation_store.header(queries.get_evaluation(db, row.id))
    assert header["seconds"] == 45.5


def test_a_session_never_opened_reports_no_duration(db):
    row = _fresh(db)
    evaluation_store.record_choice(db, row, 1)
    assert evaluation_store.header(queries.get_evaluation(db, row.id))["seconds"] is None


# MIGRATION SAFETY ------------------------------------------------------------------------


def test_a_session_recorded_before_sets_existed_is_its_own_set(db):
    legacy = {key: value for key, value in SOURCE.items() if key != "set_id"}
    legacy["id"] = "antiguo00001"
    session = EvaluationSession.from_dict(legacy)
    assert session.set_id == "antiguo00001"


def test_a_session_recorded_before_the_triage_existed_reads_as_untriaged(db):
    legacy = {key: value for key, value in SOURCE.items() if key != "triage"}
    assert EvaluationSession.from_dict(legacy).triage == {}
