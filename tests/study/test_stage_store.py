"""The arithmetic over the construction forms, pinned against hand-computed values.

Same rule as `test_evaluation_statistics.py`: every expectation here can be checked on
paper, because these are the numbers the memoria quotes about the chain itself.
"""

import csv
import io

from server import review
from study.api import stage_instruments as instruments
from study.api import stage_store as store
from study.api.admin import PROFILE_FILTERS, _narrow

GRAPH = review.KNOWLEDGE_GRAPH
PROFILE = review.EXEMPLARS_PROFILE
BANK = review.EXEMPLARS_BANK


def _form(
    artifact=GRAPH,
    overall=4,
    answers=None,
    curated=None,
    account_id=1,
    account="ana",
    profile="teacher",
    seconds=90.0,
    **extra,
):
    """One form's header, answered unless `overall` is None."""
    opened = 1000.0
    return {
        "id": extra.pop("id", 1),
        "created_at": opened,
        "updated_at": opened + seconds if overall is not None else None,
        "opened_at": opened,
        "seconds": seconds if overall is not None else None,
        "workspace": "default",
        "account_id": account_id,
        "account": account,
        "account_name": None,
        "evaluator_profile": profile,
        "artifact": artifact,
        "artifact_hash": "abc",
        "job_id": None,
        "instrument": instruments.VERSION,
        "answers": answers if answers is not None else {"effort": "touch_up"},
        "overall": overall,
        "note": None,
        "curated": curated,
        "answered": overall is not None,
        **extra,
    }


# AGGREGATES --------------------------------------------------------------------------------


def test_an_opened_but_unanswered_form_counts_apart_from_a_verdict():
    summary = store.aggregates([_form(overall=4), _form(overall=None, id=2)])

    assert summary["rows"] == 2
    assert summary["answered"] == 1
    assert summary["opened_only"] == 1
    graph = next(a for a in summary["by_artifact"] if a["artifact"] == GRAPH)
    assert graph["opened"] == 2 and graph["answered"] == 1
    assert graph["overall"]["mean"] == 4.0


def test_the_mean_and_the_distribution_are_over_answered_rows_only():
    rows = [_form(overall=2, id=1), _form(overall=5, id=2), _form(overall=None, id=3)]
    graph = store.aggregates(rows)["by_artifact"][1]

    assert graph["overall"]["mean"] == 3.5
    assert graph["overall"]["counts"] == {"1": 0, "2": 1, "3": 0, "4": 0, "5": 1}


def test_every_stage_is_reported_even_with_nothing_answered():
    summary = store.aggregates([])

    assert [a["artifact"] for a in summary["by_artifact"]] == list(review.ARTIFACTS)
    assert all(a["answered"] == 0 and a["overall"]["mean"] is None for a in summary["by_artifact"])


def test_the_questions_are_counted_in_the_instruments_own_order_with_their_wording():
    rows = [
        _form(answers={"surplus": "none", "effort": "none"}, id=1),
        _form(answers={"surplus": "many", "effort": "touch_up"}, id=2),
        _form(answers={"surplus": "none", "effort": "redo"}, id=3),
    ]
    graph = store.aggregates(rows)["by_artifact"][1]

    keys = [q["key"] for q in graph["questions"]]
    assert keys == [q["key"] for q in instruments.QUESTIONS[GRAPH]]
    surplus = graph["questions"][0]
    assert surplus["axis"] == "precision"
    assert surplus["counts"] == {"none": 2, "some": 0, "many": 1}
    assert surplus["n"] == 3
    assert [o["label"] for o in surplus["options"]] == ["Ninguno", "Alguno suelto", "Muchos"]
    # «nada» and «algún retoque» leave the artifact usable: 2 of 3.
    assert graph["usable"] == round(2 / 3, 3)


def test_an_answer_under_an_earlier_wording_is_kept_under_its_raw_value():
    graph = store.aggregates([_form(answers={"surplus": "old_value"})])["by_artifact"][1]
    surplus = graph["questions"][0]

    assert surplus["counts"]["old_value"] == 1
    assert {"value": "old_value", "label": "old_value"} in surplus["options"]


def test_the_curation_contrast_has_three_buckets_and_null_is_not_a_no():
    rows = [
        _form(overall=5, curated=True, id=1),
        _form(overall=2, curated=False, id=2),
        _form(overall=3, curated=None, id=3),
        _form(overall=4, curated=None, id=4),
    ]
    curation = store.aggregates(rows)["by_artifact"][1]["curation"]

    assert curation["yes"] == {"n": 1, "overall_mean": 5.0}
    assert curation["no"] == {"n": 1, "overall_mean": 2.0}
    assert curation["unknown"] == {"n": 2, "overall_mean": 3.5}


def test_the_median_time_on_task_ignores_rows_with_no_clock():
    rows = [_form(seconds=30.0, id=1), _form(seconds=90.0, id=2), _form(seconds=600.0, id=3)]
    graph = store.aggregates(rows)["by_artifact"][1]

    assert graph["seconds"] == {"n": 3, "median": 90.0}


# BY ACCOUNT --------------------------------------------------------------------------------


def test_by_account_says_how_far_down_the_chain_each_person_went():
    rows = [
        _form(artifact=PROFILE, id=1),
        _form(artifact=GRAPH, id=2),
        _form(artifact=BANK, overall=None, id=3),
        _form(artifact=PROFILE, account_id=2, account="bea", overall=1, id=4),
    ]
    groups = store.by_account(rows)

    assert [g["label"] for g in groups] == ["ana", "bea"]
    ana = groups[0]
    assert ana["opened"] == 3 and ana["answered"] == 2
    assert ana["per_artifact"] == {PROFILE: 1, GRAPH: 1, BANK: 0}
    assert ana["overall_mean"] == 4.0
    assert groups[1]["overall_mean"] == 1.0


def test_a_row_with_no_author_is_named_and_never_called_deleted():
    groups = store.by_account([_form(account_id=None, account=None)])

    assert groups[0]["label"] == "Sin evaluador"
    assert groups[0]["key"] == ""


# THE FILTERS -------------------------------------------------------------------------------


def test_the_profile_filter_narrows_both_instruments_the_same_way():
    rows = [_form(profile="teacher", id=1), _form(profile="student", account_id=2, id=2)]

    assert [r["id"] for r in _narrow(rows, None, "student")] == [2]
    assert [r["id"] for r in _narrow(rows, 1, None)] == [1]
    assert _narrow(rows, 1, "student") == []
    assert PROFILE_FILTERS == ("teacher", "student")


# EXPORT ------------------------------------------------------------------------------------


def _csv(rows):
    return list(csv.DictReader(io.StringIO(store.export_csv(rows))))


def test_the_export_has_one_column_per_question_key_and_keeps_the_rest():
    line = _csv([_form(answers={"surplus": "none", "effort": "redo", "legacy": "x"})])[0]

    assert line["surplus"] == "none"
    assert line["effort"] == "redo"
    assert line["tagging"] == ""
    assert line["other_answers"] == "legacy=x"
    assert line["overall"] == "4"
    assert line["answered"] == "1"
    assert line["artifact"] == GRAPH


def test_the_curation_column_is_blank_when_nobody_said():
    lines = _csv([_form(curated=None, id=1), _form(curated=True, id=2), _form(curated=False, id=3)])

    assert [line["curated"] for line in lines] == ["", "1", "0"]


def test_a_formula_planted_in_a_note_arrives_as_text():
    line = _csv([_form(note="=cmd|' /c calc'!A1")])[0]

    assert line["note"] == "'=cmd|' /c calc'!A1"


def test_a_negative_number_is_still_a_number():
    assert _csv([_form(seconds=-3.0)])[0]["seconds"] == "-3.0"


# DELETING AN EVALUATOR'S RECORDS ---------------------------------------------------------


def test_deleting_an_evaluators_records_takes_both_instruments_and_leaves_the_rest():
    import pytest
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from server.db import Base, repository
    from server.db.models import EvalSession, StageEvaluation, User
    from study.api import queries, stage_queries

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    ws = repository.ensure_workspace(db, "default")
    for uid, name in ((1, "ana"), (2, "bea")):
        db.add(User(id=uid, username=name, name=name, password_hash="x"))
    db.flush()
    for uid, sid in ((1, "s1"), (1, "s2"), (2, "s3"), (None, "stock")):
        db.add(EvalSession(id=sid, workspace_id=ws.id, user_id=uid))
    stage_queries.save(db, ws.id, 1, GRAPH, "h", instrument="3", answers={}, overall=4, note=None)
    stage_queries.save(db, ws.id, 2, GRAPH, "h", instrument="3", answers={}, overall=2, note=None)
    db.flush()

    assert queries.delete_for_accounts(db, [1]) == 2
    assert stage_queries.delete_for_accounts(db, [1]) == 1
    assert sorted(r.id for r in db.query(EvalSession).all()) == ["s3", "stock"]
    assert [r.user_id for r in db.query(StageEvaluation).all()] == [2]
    assert db.get(User, 1) is not None
    assert queries.delete_for_accounts(db, []) == 0
