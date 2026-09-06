"""Where evaluation sessions are written, and the whole arithmetic of the evaluation over them.

Sessions live in a table rather than on disk for a reason that is not tidiness: a session
recorded on disk has no evaluator, and "how the evaluations are going per account" is a question
that cannot be asked of a row that does not know whose it is.

The aggregates below are the only implementation of the evaluation's arithmetic in the codebase,
and only the administration panel reads them — never the evaluator, who must not be shown
the running score of what they are about to judge. They are computed here, next to the
definitions of what counts, rather than inside a router.
"""

import csv
import io
import json
import math
import random
import time
import uuid
from datetime import datetime

from sqlalchemy.orm import Session as DbSession

from server import csv_safe
from server.db.models import EvalSession

from .. import ARMS, EvaluationSession
from . import queries
from .instruments import RATING_SCALES, TRIAGE_VALUES

# The post-reveal rubric's own usability field, superseded by the blind triage. New sessions
# do not write it; the summaries still read it, so sessions recorded under the old
# instrument keep aggregating instead of vanishing.
USABILITY_VALUES = ("as_is", "with_edits", "no")


# WRITE -----------------------------------------------------------------------------------------


def save(
    db: DbSession, workspace_id: int, user_id: int | None, session: EvaluationSession
) -> EvalSession:
    """Write a freshly produced session to its own row."""
    return queries.upsert_evaluation(db, session.id, workspace_id, user_id, session.to_dict())


def assign(
    db: DbSession,
    source: EvalSession,
    user_id: int,
    assigned_by: int,
    seed: int | None = None,
    allow_repeat: bool = False,
) -> EvaluationSession:
    """Copy the three items into a new row for somebody else, judgement cleared.

    The shuffle is DRAWN AFRESH, because two evaluators sharing an order share a position
    bias and an agreement that includes it is not an agreement about the exercises. `think`
    is INHERITED and never redrawn: those items were generated under a reasoning condition
    that already happened. Raises ValueError('already-assigned') unless `allow_repeat`,
    since the usual cause of a second copy is a double click.
    """
    set_id = source.set_id or source.id
    if not allow_repeat:
        for row in queries.sessions_in_set(db, set_id):
            if row.user_id == user_id:
                raise ValueError("already-assigned")

    seed = random.randrange(2**31) if seed is None else int(seed)
    order = list(ARMS)
    random.Random(seed).shuffle(order)

    session = EvaluationSession.from_dict(source.trace)
    session.id = uuid.uuid4().hex[:12]
    session.created_at = time.time()
    session.set_id = set_id
    session.assigned_by = assigned_by
    session.seed = seed
    session.shuffle = order
    session.triage = {}
    session.choice = None
    session.choice_arm = None
    session.chosen_at = None
    session.opened_at = None
    session.declined_at = None
    session.evaluator_note = None
    session.rating = None

    queries.upsert_evaluation(db, session.id, source.workspace_id, user_id, session.to_dict())
    return session


def load(db: DbSession, session_id: str) -> EvaluationSession | None:
    """Rebuild one session from its stored trace, or None if there is no such row."""
    row = queries.get_evaluation(db, session_id)
    if row is None:
        return None
    return EvaluationSession.from_dict(row.trace)


def record_choice(
    db: DbSession, row: EvalSession, choice: int | None, note: str | None = None
) -> EvaluationSession:
    """Record the forced choice by POSITION and stamp `chosen_at`, which reveals the session."""
    session = EvaluationSession.from_dict(row.trace)
    if session.finished:
        raise ValueError("already-chosen")
    if choice is not None and choice not in (1, 2, 3):
        raise ValueError("choice must be 1, 2, 3 or null")

    session.choice = choice
    session.choice_arm = session.arm_at(choice) if choice is not None else None
    session.chosen_at = time.time()
    session.evaluator_note = (note or "").strip() or None
    queries.upsert_evaluation(db, session.id, row.workspace_id, row.user_id, session.to_dict())
    return session


def record_triage(
    db: DbSession, row: EvalSession, position: int, value: str
) -> EvaluationSession:
    """Record one blind per-card answer, stored BY POSITION.

    It has to arrive before the choice: the whole value of the triage is that it was given
    without knowing which architecture wrote which card.
    """
    session = EvaluationSession.from_dict(row.trace)
    if session.finished:
        raise ValueError("already-chosen")
    if position not in (1, 2, 3):
        raise ValueError("position must be 1, 2 or 3")
    if value not in TRIAGE_VALUES:
        raise ValueError(f"'{value}' must be one of {list(TRIAGE_VALUES)}")

    session.triage = {**session.triage, str(position): value}
    queries.upsert_evaluation(db, session.id, row.workspace_id, row.user_id, session.to_dict())
    return session


def record_decline(
    db: DbSession, row: EvalSession, note: str | None = None
) -> EvaluationSession:
    """Close the session as unjudgeable, setting `declined_at` and NOT `chosen_at`.

    A decline is not a preference: nothing this person could not judge ever reaches a
    preference count.
    """
    session = EvaluationSession.from_dict(row.trace)
    if session.finished:
        raise ValueError("already-chosen")

    session.declined_at = time.time()
    session.evaluator_note = (note or "").strip() or None
    queries.upsert_evaluation(db, session.id, row.workspace_id, row.user_id, session.to_dict())
    return session


def mark_opened(db: DbSession, row: EvalSession) -> None:
    """Start the time-on-task clock, once, on the first read by whoever has to judge.

    A later read never moves it: restarting it on a reload would turn a session somebody
    left open overnight into one they answered in four seconds.
    """
    if row.opened_at is not None:
        return
    session = EvaluationSession.from_dict(row.trace)
    session.opened_at = time.time()
    queries.upsert_evaluation(db, session.id, row.workspace_id, row.user_id, session.to_dict())


def record_rating(db: DbSession, row: EvalSession, rating: dict) -> EvaluationSession:
    """Record the post-reveal rubric, refusing it until a choice exists."""
    session = EvaluationSession.from_dict(row.trace)
    if not session.decided:
        raise ValueError("not-chosen-yet")

    session.rating = _clean_rating(rating)
    queries.upsert_evaluation(db, session.id, row.workspace_id, row.user_id, session.to_dict())
    return session


def _clean_rating(rating: dict) -> dict:
    """Validate the rubric here and not only in the browser.

    A value out of range poisons every mean computed for the memoria, and there is no way
    to tell afterwards.
    """
    clean: dict = {"arm": rating.get("arm") or "system", "rated_at": time.time()}
    for name in RATING_SCALES:
        value = rating.get(name)
        if value is None:
            continue
        number = int(value)
        if not 1 <= number <= 5:
            raise ValueError(f"'{name}' must be between 1 and 5, got {number}")
        clean[name] = number
    usability = rating.get("usability")
    if usability is not None:
        if usability not in USABILITY_VALUES:
            raise ValueError(f"'usability' must be one of {list(USABILITY_VALUES)}")
        clean["usability"] = usability
    comment = (rating.get("comment") or "").strip()
    if comment:
        clean["comment"] = comment
    return clean


# READ ------------------------------------------------------------------------------------------


def listing(
    db: DbSession,
    workspace_id: int,
    author: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return one page of headers with the total, for the evaluator's own listing."""
    rows, total = queries.list_evaluations(
        db, workspace_id=workspace_id, author=author, limit=limit, offset=offset
    )
    return [header(row) for row in rows], total


def header(row: EvalSession, user=None, workspace_slug: str | None = None) -> dict:
    """Flatten one row into the shape every aggregate and the CSV are written against."""
    shuffle = list(row.shuffle or [])
    triage = dict(row.triage or {})
    return {
        "id": row.id,
        "created_at": row.created_at.timestamp() if row.created_at else 0.0,
        "job_id": row.job_id,
        "set_id": row.set_id or row.id,
        "assigned": row.assigned_by is not None,
        "concepts": list(row.concepts or []),
        "item_type": row.item_type or "",
        "fixed": dict(row.fixed or {}),
        "curriculum": list(row.curriculum or []),
        "instructions": row.instructions or "",
        "seed": row.seed,
        "shuffle": shuffle,
        "think": bool(row.think),
        "triage": triage,
        # Re-keyed here rather than stored, so the raw record keeps saying what the person
        # actually saw and the mapping stays derivable from the seed.
        "triage_arm": _by_arm(triage, shuffle),
        "choice": row.choice,
        "choice_arm": row.choice_arm,
        "chosen_at": row.chosen_at,
        "opened_at": row.opened_at,
        "declined_at": row.declined_at,
        "seconds": _seconds(row.opened_at, row.chosen_at or row.declined_at),
        "evaluator_note": row.evaluator_note,
        "rating": row.rating,
        "arm_status": dict(row.arm_status or {}),
        "arm_elapsed_ms": dict(row.arm_elapsed_ms or {}),
        "account_id": row.user_id,
        **_account_fields(user),
        "workspace": workspace_slug,
    }


def _by_arm(triage: dict, shuffle: list) -> dict:
    """Re-key answers given by position into answers by architecture."""
    mapped = {}
    for position, value in triage.items():
        index = int(position) - 1
        if 0 <= index < len(shuffle):
            mapped[shuffle[index]] = value
    return mapped


def _seconds(opened: float | None, ended: float | None) -> float | None:
    """Return the time on task, or None when either end is missing or out of order."""
    if not opened or not ended or ended < opened:
        return None
    return round(ended - opened, 1)


def _account_fields(user) -> dict:
    """Name the evaluator, or leave the three columns blank when the row has no author."""
    if user is None:
        return {"account": None, "account_name": None, "evaluator_profile": None}
    return {
        "account": user.username,
        "account_name": user.name,
        "evaluator_profile": user.evaluator_profile,
    }


# AGGREGATES ------------------------------------------------------------------------------------


def aggregates(headers: list[dict]) -> dict:
    """Summarise a population: preferences, significance, triage, position and duration.

    Everything per-arm is counted over DECIDED sessions only, and that is a blinding
    requirement rather than a statistical preference: with a session still waiting to be
    judged, "naive: unavailable 1" beside a card that shows no exercise names the card.
    """
    decided = [h for h in headers if h.get("chosen_at")]
    declined = [h for h in headers if h.get("declined_at")]
    preferences = _preferences(decided)

    status_counts = {arm: {} for arm in ARMS}
    for row in decided:
        for arm, status in (row.get("arm_status") or {}).items():
            status_counts.setdefault(arm, {})
            status_counts[arm][status] = status_counts[arm].get(status, 0) + 1

    return {
        "sessions": len(headers),
        "decided": len(decided),
        "declined": len(declined),
        "rated": sum(1 for h in headers if h.get("rating")),
        "preferences": preferences,
        "arm_status": status_counts,
        "rubric": _rubric_summary([h["rating"] for h in headers if h.get("rating")]),
        "think": _think_breakdown(decided),
        "elapsed_ms": _mean_elapsed(decided),
        # The three answers the memoria has to be able to give: is the preference
        # distinguishable from chance, how wide is it, and did a card's position decide any
        # of it.
        "significance": significance(preferences, len(decided)),
        "triage": triage_summary(decided),
        "position": position_bias(decided),
        "duration": _duration_summary(decided),
    }


def headers(db: DbSession, workspace_id: int | None = None) -> list[dict]:
    """Read the whole population as headers, each carrying its author and its workspace."""
    return [
        header(row, user, row.workspace.slug if row.workspace else None)
        for row, user in queries.all_evaluations(db, workspace_id)
    ]


def _preferences(rows: list[dict]) -> dict:
    """Count which arm won, with "none" for an explicitly registered no-preference."""
    counts = {arm: 0 for arm in ARMS}
    counts["none"] = 0
    for row in rows:
        counts[row.get("choice_arm") or "none"] += 1
    return counts


# STATISTICS ------------------------------------------------------------------------------
#
# Written out with stdlib `math` rather than reached for from scipy, whose 115 MB the
# runtime stopped paying for. The three tests the evaluation needs are a handful of lines each.


def significance(preferences: dict, decided: int) -> dict:
    """Is the preference for the system distinguishable from picking one of three at random?"""
    expected = 1 / len(ARMS)
    summary: dict = {"n": decided, "expected": round(expected, 4), "arms": {}}
    for arm in ARMS:
        wins = preferences.get(arm, 0)
        summary["arms"][arm] = {
            "wins": wins,
            "share": round(wins / decided, 4) if decided else None,
            "ci95": wilson(wins, decided),
            "p": (round(p, 5) if (p := binomial_p(wins, decided, expected)) is not None else None),
        }
    return summary


def binomial_p(successes: int, total: int, expected: float) -> float | None:
    """Return the EXACT two-sided binomial p, by the method of small p-values.

    Exact rather than normal-approximated because the evaluation's n is in the dozens, which is
    precisely where the approximation stops being one.
    """
    if total <= 0:
        return None
    observed = _binomial_pmf(successes, total, expected)
    # Floating point makes "equally likely" a knife edge, and without a tolerance the
    # symmetric case silently loses its own mirror image.
    tolerance = observed * 1e-7
    return min(
        1.0,
        sum(
            _binomial_pmf(k, total, expected)
            for k in range(total + 1)
            if _binomial_pmf(k, total, expected) <= observed + tolerance
        ),
    )


def _binomial_pmf(k: int, n: int, p: float) -> float:
    """Return the probability of exactly k successes in n trials at rate p."""
    return math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))


def position_bias(decided: list[dict]) -> dict:
    """Ask whether the position of a card decided anything, by chi-square on three counts.

    It costs nothing because the seed and the order were recorded from the first session.
    """
    counts = {1: 0, 2: 0, 3: 0}
    for row in decided:
        choice = row.get("choice")
        if choice in counts:
            counts[choice] += 1

    total = sum(counts.values())
    if total == 0:
        return {"n": 0, "counts": counts, "p": None}

    expected = total / 3
    statistic = sum((observed - expected) ** 2 / expected for observed in counts.values())
    return {
        "n": total,
        "counts": counts,
        "chi2": round(statistic, 4),
        "p": round(_chi2_p_df2(statistic), 5),
    }


def _chi2_p_df2(statistic: float) -> float:
    """Return the chi-square survival for the 2 degrees of freedom three positions leave.

    That case has the closed form exp(-x/2): no table, no library, no approximation.
    """
    return math.exp(-statistic / 2)


def triage_summary(decided: list[dict]) -> dict:
    """Summarise the blind per-card answer, the one quality signal all three arms have.

    `usable` folds "tal cual" and "con retoques" together, because that is the question a
    teacher is really answering; `outright` keeps the stricter reading beside it.
    """
    summary: dict = {}
    for arm in ARMS:
        counts = {value: 0 for value in TRIAGE_VALUES}
        for row in decided:
            value = (row.get("triage_arm") or {}).get(arm)
            if value in counts:
                counts[value] += 1
        total = sum(counts.values())
        if not total:
            continue
        summary[arm] = {
            "n": total,
            "counts": counts,
            "usable": round((counts["yes"] + counts["partly"]) / total, 4),
            "outright": round(counts["yes"] / total, 4),
            "ci95_usable": wilson(counts["yes"] + counts["partly"], total),
        }
    return summary


def wilson(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    """Return a WILSON 95 % interval, never the textbook normal one.

    At these counts the textbook formula puts a bound below zero or above one, and a
    5-of-5 preference is exactly the case this evaluation will meet.
    """
    if total <= 0:
        return None
    phat = successes / total
    denominator = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, centre - spread), 4), round(min(1.0, centre + spread), 4)]


def _duration_summary(decided: list[dict]) -> dict:
    """Report how long judgements took, which is how one decided without reading is noticed.

    The MEDIAN and not the mean: one comparison left open over a weekend drags an average
    into meaninglessness, and that is the common case rather than the odd one.
    """
    values = sorted(s for h in decided if isinstance(s := h.get("seconds"), (int, float)))
    if not values:
        return {"n": 0}
    middle = len(values) // 2
    median = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2
    return {
        "n": len(values),
        "median": round(median, 1),
        "fastest": values[0],
        "slowest": values[-1],
        "under_20s": sum(1 for value in values if value < 20),
    }


def _think_breakdown(decided: list[dict]) -> dict:
    """Split the decided sessions by the reasoning mode their seed drew.

    Only the two LOCAL arms have their timings averaged: the commercial one deliberates or
    not according to its provider, so the flag never reaches it.
    """
    breakdown = {}
    for key, wanted in (("on", True), ("off", False)):
        rows = [h for h in decided if bool(h.get("think", True)) is wanted]
        preferences = _preferences(rows)
        elapsed = {}
        for arm in ("rag", "system"):
            timings = [(h.get("arm_elapsed_ms") or {}).get(arm) for h in rows]
            values = [ms for ms in timings if isinstance(ms, (int, float)) and ms > 0]
            if values:
                elapsed[arm] = round(sum(values) / len(values))
        breakdown[key] = {
            "decided": len(rows),
            "preferences": preferences,
            "elapsed_ms": elapsed,
            "rubric": _rubric_summary([h["rating"] for h in rows if h.get("rating")]),
        }
    return breakdown


def _rubric_summary(ratings: list[dict]) -> dict:
    """Average the four post-reveal scales, and report `complexity` twice.

    `complexity` is NOT "more is better": a 5 is as wrong as a 1 and the target is 3, so
    the mean distance to 3 goes beside the raw mean, which alone reads as a quality score.
    """
    summary: dict = {"n": len(ratings)}
    for name in RATING_SCALES:
        values = [r[name] for r in ratings if isinstance(r.get(name), int)]
        if not values:
            continue
        summary[name] = {
            "mean": round(sum(values) / len(values), 2),
            "n": len(values),
        }
        if name == "complexity":
            distances = [abs(v - 3) for v in values]
            summary[name]["mean_distance_to_3"] = round(sum(distances) / len(distances), 2)
    usability = [r["usability"] for r in ratings if r.get("usability")]
    if usability:
        summary["usability"] = {
            value: usability.count(value) for value in USABILITY_VALUES
        }
    return summary


def _mean_elapsed(rows: list[dict]) -> dict:
    """Average each arm's wall time, ignoring the arms that produced nothing."""
    means = {}
    for arm in ARMS:
        values = [
            ms
            for ms in ((h.get("arm_elapsed_ms") or {}).get(arm) for h in rows)
            if isinstance(ms, (int, float)) and ms > 0
        ]
        if values:
            means[arm] = round(sum(values) / len(values))
    return means


def by_account(headers: list[dict]) -> list[dict]:
    """Group by evaluator, which is how the evaluation is actually read.

    `sessions` and `decided` stay separate: somebody who launched twenty comparisons and
    judged three has contributed three data points.
    """
    return _grouped(headers, key="account_id", label_of=_account_label)


def by_workspace(headers: list[dict]) -> list[dict]:
    """Group by instance, so a subject's own results can be read apart."""
    return _grouped(headers, key="workspace", label_of=lambda h: h.get("workspace") or "—")


PROFILE_LABELS = {"teacher": "Docentes", "student": "Alumnos", None: "Sin perfil"}


def by_profile(headers: list[dict]) -> list[dict]:
    """Group by teacher and student, which the mixed panel makes a separate question.

    A student and a teacher were not even asked the same thing about the card, so
    dissolving the two into one mean answers nothing.
    """
    return _grouped(
        headers,
        key="evaluator_profile",
        label_of=lambda h: PROFILE_LABELS.get(h.get("evaluator_profile"), "Sin perfil"),
    )


# AGREEMENT -------------------------------------------------------------------------------


def agreement(headers: list[dict]) -> dict:
    """Pool what two people who judged the SAME three items said.

    The only evidence the evaluation can offer that its instrument is reproducible rather than a
    record of one person's taste. `declined` sessions are excluded on both sides: an
    absence of judgement is not an agreement.
    """
    by_set: dict[str, list[dict]] = {}
    for row in headers:
        if row.get("chosen_at"):
            by_set.setdefault(row.get("set_id") or row["id"], []).append(row)

    shared = {key: rows for key, rows in by_set.items() if len(rows) > 1}
    choice_pairs: list[tuple[str, str]] = []
    triage_pairs: list[tuple[str, str]] = []

    for rows in shared.values():
        for left, right in _comparable_pairs(rows):
            choice_pairs.append(
                (left.get("choice_arm") or "none", right.get("choice_arm") or "none")
            )
            triage_pairs.extend(_shared_triage(left, right))

    return {
        "sets_shared": len(shared),
        "choice": _pooled_kappa(choice_pairs),
        "triage": _pooled_kappa(triage_pairs),
    }


def _comparable_pairs(rows: list[dict]):
    """Yield every pair of judgements of one set made by two DIFFERENT accounts.

    Two judgements by the same account are consistency, not agreement, and pooling them
    here would flatter the number.
    """
    for first in range(len(rows)):
        for second in range(first + 1, len(rows)):
            left, right = rows[first], rows[second]
            account = left.get("account_id")
            if account is not None and account == right.get("account_id"):
                continue
            yield left, right


def _shared_triage(left: dict, right: dict) -> list[tuple[str, str]]:
    """Return the blind answers both evaluators gave, for the arms both of them answered."""
    left_triage = left.get("triage_arm") or {}
    right_triage = right.get("triage_arm") or {}
    return [
        (left_triage[arm], right_triage[arm])
        for arm in ARMS
        if arm in left_triage and arm in right_triage
    ]


def _pooled_kappa(pairs: list[tuple[str, str]]) -> dict:
    """Return SCOTT'S π over pooled pairs, which is not Cohen's κ and must not be called it.

    This panel is not a fixed pair of raters — evaluators teach different subjects and
    overlap where an administrator decided they should — so the chance term is a single
    pooled marginal. The memoria has to say so rather than label the number κ.
    """
    if not pairs:
        return {"pairs": 0}

    observed = sum(1 for left, right in pairs if left == right) / len(pairs)

    frequency: dict[str, int] = {}
    for left, right in pairs:
        frequency[left] = frequency.get(left, 0) + 1
        frequency[right] = frequency.get(right, 0) + 1
    total = 2 * len(pairs)
    expected = sum((count / total) ** 2 for count in frequency.values())

    return {
        "pairs": len(pairs),
        "observed": round(observed, 4),
        "expected": round(expected, 4),
        # Everybody answering the same thing every time leaves nothing to correct for, and
        # the formula divides by zero saying so. Reported as null, never as perfect.
        "kappa": (round((observed - expected) / (1 - expected), 4) if expected < 1 else None),
    }


def _account_label(row: dict) -> str:
    """Name the evaluator, or "Sin evaluador" — never "cuenta borrada".

    `account_id` goes null for two reasons and only one is a deletion: stock has no
    evaluator until somebody is handed a copy, and calling that data loss reads as an
    incident.
    """
    return row.get("account") or row.get("account_name") or "Sin evaluador"


def _grouped(headers: list[dict], key: str, label_of) -> list[dict]:
    """Bucket the headers by one field and aggregate each bucket, busiest group first."""
    buckets: dict[object, list[dict]] = {}
    for row in headers:
        buckets.setdefault(row.get(key), []).append(row)

    groups = []
    for value, rows in buckets.items():
        summary = aggregates(rows)
        groups.append(
            {
                "key": value if value is not None else "",
                "label": label_of(rows[0]),
                "name": rows[0].get("account_name"),
                # The profile of the group's first row: exact when grouping by account,
                # and what the panel's evaluator table reads beside the name.
                "evaluator_profile": rows[0].get("evaluator_profile"),
                "last_at": max(r.get("created_at") or 0 for r in rows),
                **summary,
            }
        )
    return sorted(groups, key=lambda g: (-g["sessions"], g["label"]))


def per_day(headers: list[dict]) -> list[dict]:
    """Count sessions and decisions per calendar day.

    One point per day is how the panel says whether the evaluation is still collecting data or
    stopped three weeks ago, which no mean can answer.
    """
    counts: dict[str, dict] = {}
    for row in headers:
        stamp = row.get("created_at") or 0
        if not stamp:
            continue
        day = datetime.fromtimestamp(stamp).date().isoformat()
        bucket = counts.setdefault(day, {"day": day, "sessions": 0, "decided": 0})
        bucket["sessions"] += 1
        if row.get("chosen_at"):
            bucket["decided"] += 1
    return [counts[day] for day in sorted(counts)]


# EXPORT ----------------------------------------------------------------------------------------


def export_csv(headers: list[dict]) -> str:
    """Render the evaluation's raw data: one row per session, oldest first.

    `columns` is the authoritative order and `DictWriter` reindexes every line against it.
    Restricted to the installation's administrator, because a per-session export of
    everybody's judgements is research data and not a feature of the evaluation screen.
    """
    columns = [
        "session_id",
        "created_at",
        "workspace",
        "account",
        "evaluator_profile",
        "set_id",
        "assigned",
        "job_id",
        "item_type",
        "concepts",
        "curriculum",
        "fixed",
        "instructions",
        "seed",
        "think",
        "position_1",
        "position_2",
        "position_3",
        *[f"triage_{arm}" for arm in ARMS],
        "choice",
        "choice_arm",
        "chosen_at",
        "declined",
        "seconds",
        "evaluator_note",
        *[f"{arm}_status" for arm in ARMS],
        *[f"{arm}_ms" for arm in ARMS],
        *RATING_SCALES,
        "usability",
        "rating_comment",
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in sorted(headers, key=lambda h: h.get("created_at") or 0):
        writer.writerow(csv_safe.row(_export_row(row)))
    return buffer.getvalue()


def _export_row(row: dict) -> dict:
    """Build one line of the export from the blocks above, plus the four rubric scales."""
    rating = row.get("rating") or {}
    return {
        **_export_commission(row),
        **_export_judgement(row, rating),
        **_export_positions(row.get("shuffle") or []),
        **_export_arms(row),
        **{name: rating.get(name, "") for name in RATING_SCALES},
    }


def _export_commission(row: dict) -> dict:
    """The columns identifying one session and the commission behind it."""
    return {
        "session_id": row["id"],
        "created_at": _iso(row.get("created_at")),
        "workspace": row.get("workspace") or "",
        "account": row.get("account") or "",
        "evaluator_profile": row.get("evaluator_profile") or "",
        "set_id": row.get("set_id") or row["id"],
        "assigned": int(bool(row.get("assigned"))),
        "job_id": row.get("job_id") or "",
        "item_type": row.get("item_type") or "",
        "concepts": "|".join(row.get("concepts") or []),
        "curriculum": "|".join(row.get("curriculum") or []),
        "fixed": json.dumps(row.get("fixed") or {}, ensure_ascii=False),
        "instructions": row.get("instructions") or "",
        "seed": row.get("seed"),
        "think": int(bool(row.get("think", True))),
    }


def _export_judgement(row: dict, rating: dict) -> dict:
    """The columns recording what the evaluator answered and how long it took them."""
    return {
        "choice": row.get("choice") if row.get("choice") is not None else "",
        "choice_arm": row.get("choice_arm") or "",
        "chosen_at": _iso(row.get("chosen_at")),
        "declined": int(bool(row.get("declined_at"))),
        "seconds": row.get("seconds") if row.get("seconds") is not None else "",
        "evaluator_note": row.get("evaluator_note") or "",
        "usability": rating.get("usability", ""),
        "rating_comment": rating.get("comment", ""),
    }


def _iso(timestamp: float | None) -> str:
    """Render a POSIX timestamp as a local ISO string to the second, or as empty."""
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


def _export_positions(shuffle: list) -> dict:
    """Which arm sat at each of the three positions, so the blinding stays auditable."""
    return {
        f"position_{index + 1}": shuffle[index] if index < len(shuffle) else ""
        for index in range(3)
    }


def _export_arms(row: dict) -> dict:
    """The blind triage, the status and the timing, one column per arm."""
    triage = row.get("triage_arm") or {}
    status = row.get("arm_status") or {}
    elapsed = row.get("arm_elapsed_ms") or {}
    line: dict = {}
    for arm in ARMS:
        line[f"triage_{arm}"] = triage.get(arm, "")
        line[f"{arm}_status"] = status.get(arm, "")
        line[f"{arm}_ms"] = elapsed.get(arm, "")
    return line
