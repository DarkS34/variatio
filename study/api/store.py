"""Where evaluation sessions live, and the arithmetic of the study over them.

Two files per workspace until phase 3 — `sessions.jsonl` for the headers, `<id>.json` for
the trace — and one table since, for a reason that is not tidiness: a session recorded on
disk has no evaluator, and «cómo van las evaluaciones por cuenta» is a question that
cannot be asked of a row that does not know whose it is. The header/trace split survives
as columns versus `trace`, so listing a hundred sessions still does not load a hundred
prompts.

The aggregate functions below are the only implementation of the study's arithmetic in
the codebase. They used to feed the evaluator's own screen as well; since phase 3 that
screen shows a person their sessions and nothing else, and these numbers are read only by
the administration panel — but they are computed here, next to the definitions of what
counts, rather than inside a router.
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

# The post-reveal rubric's own usability field, from before the question moved to the blind
# triage where it belongs. New sessions do not write it; the summaries still read it so the
# sessions recorded under the old instrument keep aggregating instead of vanishing.
USABILITY_VALUES = ("as_is", "with_edits", "no")


# WRITE -----------------------------------------------------------------------------------------


def save(
    db: DbSession, workspace_id: int, user_id: int | None, session: EvaluationSession
) -> EvalSession:
    return queries.upsert_evaluation(db, session.id, workspace_id, user_id, session.to_dict())


# Hand the same three items to somebody else. THE ITEMS ARE COPIED, THE JUDGEMENT IS NOT:
# a fresh row with an order of its own and every answer cleared, so what the two evaluators
# end up agreeing about is the exercises and not the seating.
#
# `think` is inherited rather than redrawn, and that is the one place a copy's seed means
# less than the original's: these three items were generated under a reasoning condition
# that already happened, and drawing a new one would record a lie about how they were made.
# The shuffle is what the seed decides here.
def assign(
    db: DbSession,
    source: EvalSession,
    user_id: int,
    assigned_by: int,
    seed: int | None = None,
    allow_repeat: bool = False,
) -> EvaluationSession:
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
    row = queries.get_evaluation(db, session_id)
    if row is None:
        return None
    return EvaluationSession.from_dict(row.trace)


def record_choice(
    db: DbSession, row: EvalSession, choice: int | None, note: str | None = None
) -> EvaluationSession:
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


# One card, one answer, and it has to arrive BEFORE the choice: the whole value of the
# triage is that it was given without knowing which architecture wrote which card.
def record_triage(
    db: DbSession, row: EvalSession, position: int, value: str
) -> EvaluationSession:
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


# The evaluator is outside the subject of these three items. It ends the session like a
# choice does and is deliberately NOT one: `chosen_at` stays empty, so nothing this person
# could not judge ever reaches a preference count.
def record_decline(
    db: DbSession, row: EvalSession, note: str | None = None
) -> EvaluationSession:
    session = EvaluationSession.from_dict(row.trace)
    if session.finished:
        raise ValueError("already-chosen")

    session.declined_at = time.time()
    session.evaluator_note = (note or "").strip() or None
    queries.upsert_evaluation(db, session.id, row.workspace_id, row.user_id, session.to_dict())
    return session


# First read wins, and a later one never moves it: this is the clock «cuánto tardó» is
# measured against, and restarting it on a reload would turn a session someone left open
# overnight into one they answered in four seconds.
def mark_opened(db: DbSession, row: EvalSession) -> None:
    if row.opened_at is not None:
        return
    session = EvaluationSession.from_dict(row.trace)
    session.opened_at = time.time()
    queries.upsert_evaluation(db, session.id, row.workspace_id, row.user_id, session.to_dict())


def record_rating(db: DbSession, row: EvalSession, rating: dict) -> EvaluationSession:
    session = EvaluationSession.from_dict(row.trace)
    if not session.decided:
        raise ValueError("not-chosen-yet")

    session.rating = _clean_rating(rating)
    queries.upsert_evaluation(db, session.id, row.workspace_id, row.user_id, session.to_dict())
    return session


# The rubric is validated here and not only in the browser: a value out of range poisons
# every mean computed for the memoria, and there is no way to tell afterwards.
def _clean_rating(rating: dict) -> dict:
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


# The shape the aggregates below are written against, kept identical to the JSONL header
# it replaces so that arithmetic verified on the old records still applies to the new
# rows. `account` and `workspace` are the two fields the file never had.
def header(row: EvalSession, user=None, workspace_slug: str | None = None) -> dict:
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
        "account": (user.username if user is not None else None),
        "account_name": (user.name if user is not None else None),
        "evaluator_profile": (user.evaluator_profile if user is not None else None),
        "workspace": workspace_slug,
    }


def _by_arm(triage: dict, shuffle: list) -> dict:
    mapped = {}
    for position, value in triage.items():
        index = int(position) - 1
        if 0 <= index < len(shuffle):
            mapped[shuffle[index]] = value
    return mapped


def _seconds(opened: float | None, ended: float | None) -> float | None:
    if not opened or not ended or ended < opened:
        return None
    return round(ended - opened, 1)


def listing(
    db: DbSession,
    workspace_id: int,
    author: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    rows, total = queries.list_evaluations(
        db, workspace_id=workspace_id, author=author, limit=limit, offset=offset
    )
    return [header(row) for row in rows], total


# AGGREGATES ------------------------------------------------------------------------------------


# Everything per-arm is counted over DECIDED sessions only, and that is a blinding
# requirement, not a statistical preference: with a session still waiting to be judged,
# "naive: unavailable 1" next to a card that shows no exercise names the card.
def headers(db: DbSession, workspace_id: int | None = None) -> list[dict]:
    return [
        header(row, user, row.workspace.slug if row.workspace else None)
        for row, user in queries.all_evaluations(db, workspace_id)
    ]


def aggregates(headers: list[dict]) -> dict:
    decided = [h for h in headers if h.get("chosen_at")]
    declined = [h for h in headers if h.get("declined_at")]

    preferences = {arm: 0 for arm in ARMS}
    preferences["none"] = 0
    for row in decided:
        preferences[row.get("choice_arm") or "none"] += 1

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
        # The three answers the memoria has to be able to give and could not before: is the
        # preference distinguishable from chance, how wide is it, and did the position of a
        # card decide any of it.
        "significance": significance(preferences, len(decided)),
        "triage": triage_summary(decided),
        "position": position_bias(decided),
        "duration": _duration_summary(decided),
    }


# STATISTICS ------------------------------------------------------------------------------
#
# Written out with `math` rather than reached for from scipy, and that is not stubbornness:
# scipy left `dependencies` on 2026-08-24 after 115 MB were found to be paid for an import
# that never happened, and the three tests the study needs are each a handful of lines.


def _binomial_pmf(k: int, n: int, p: float) -> float:
    return math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))


# Exact two-sided binomial, by the method of small p-values: everything at least as
# unlikely as what was seen. Exact rather than normal-approximated because the study's n is
# in the dozens, which is precisely where the approximation stops being one.
def binomial_p(successes: int, total: int, expected: float) -> float | None:
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


# Wilson rather than the textbook normal interval, which at these counts can put a bound
# below zero or above one and is visibly wrong at the extremes — a 5-of-5 preference is
# exactly the case the study will meet and exactly the one the textbook formula fumbles.
def wilson(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    if total <= 0:
        return None
    phat = successes / total
    denominator = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, centre - spread), 4), round(min(1.0, centre + spread), 4)]


# Chi-square survival with 2 degrees of freedom, which is what three categories leave and
# which happens to have a closed form: exp(-x/2). No table, no library, no approximation.
def _chi2_p_df2(statistic: float) -> float:
    return math.exp(-statistic / 2)


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


# The check Chatbot Arena had to run after publishing, and which costs nothing here because
# the seed and the order were recorded from the first session: did the letter on the card
# decide anything? Three positions, so two degrees of freedom.
def position_bias(decided: list[dict]) -> dict:
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


# The blind per-card answer, which is the only quality signal in the study that exists for
# all three architectures. `usable` folds «tal cual» and «con retoques» together because
# that is the question a teacher is really answering — would this save me work — while
# `outright` keeps the stricter reading beside it rather than instead of it.
def triage_summary(decided: list[dict]) -> dict:
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


# How long a judgement took, which is how a session decided without reading one gets
# noticed. The median and not the mean: one comparison left open over a weekend would drag
# an average into meaninglessness, and that is the common case rather than the odd one.
def _duration_summary(decided: list[dict]) -> dict:
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


# The reasoning mode is drawn per session, so the answer to "does it buy anything?" is
# this split and nothing else. Over DECIDED sessions only, like every other per-arm count
# here: a pending session must not move a number that its own evaluator can see.
#
# The two local arms are the only ones the flag reaches — the commercial one deliberates
# or not according to its provider — so only their timings are averaged.
def _think_breakdown(decided: list[dict]) -> dict:
    breakdown = {}
    for key, wanted in (("on", True), ("off", False)):
        rows = [h for h in decided if bool(h.get("think", True)) is wanted]
        preferences = {arm: 0 for arm in ARMS}
        preferences["none"] = 0
        for row in rows:
            preferences[row.get("choice_arm") or "none"] += 1
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


def _mean_elapsed(rows: list[dict]) -> dict:
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


# `complexity` is NOT "more is better": a 5 is as wrong as a 1 and the target is 3, so
# the distance to 3 is reported alongside the raw mean. Publishing the raw mean alone
# would invite reading it as a quality score.
def _rubric_summary(ratings: list[dict]) -> dict:
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


# One row per account, which is the grouping the study is actually read by. `sessions` and
# `decided` are separate on purpose: a person who launched twenty comparisons and judged
# three has contributed three data points, and a table that showed only the first number
# would say the opposite.
def by_account(headers: list[dict]) -> list[dict]:
    return _grouped(headers, key="account_id", label_of=_account_label)


def by_workspace(headers: list[dict]) -> list[dict]:
    return _grouped(headers, key="workspace", label_of=lambda h: h.get("workspace") or "—")


PROFILE_LABELS = {"teacher": "Docentes", "student": "Alumnos", None: "Sin perfil"}


# The panel is deliberately mixed, so «¿se sostiene la preferencia en los dos perfiles?» is
# a question the study has to be able to answer separately rather than dissolve into one
# mean. A student and a teacher were not even asked the same question about the card.
def by_profile(headers: list[dict]) -> list[dict]:
    return _grouped(
        headers,
        key="evaluator_profile",
        label_of=lambda h: PROFILE_LABELS.get(h.get("evaluator_profile"), "Sin perfil"),
    )


# AGREEMENT -------------------------------------------------------------------------------


# What two people who judged the SAME three items said, which is the only evidence the study
# can offer that its instrument is reproducible rather than a record of one person's taste.
#
# Pooled over every pair of evaluators that shares a set, rather than computed for a fixed
# pair of raters, because this panel is not one: evaluators teach different subjects and
# overlap where an administrator decided they should. That makes the chance term a single
# pooled marginal — Scott's π rather than Cohen's κ proper — and the difference is worth
# stating in the memoria instead of quietly labelling the number κ.
#
# `declined` sessions are excluded on both sides: «no me veo capacitado» is the absence of a
# judgement, and counting two absences as an agreement would reward putting the wrong people
# in front of the wrong subject.
def agreement(headers: list[dict]) -> dict:
    by_set: dict[str, list[dict]] = {}
    for row in headers:
        if row.get("chosen_at"):
            by_set.setdefault(row.get("set_id") or row["id"], []).append(row)

    shared = {key: rows for key, rows in by_set.items() if len(rows) > 1}
    choice_pairs: list[tuple[str, str]] = []
    triage_pairs: list[tuple[str, str]] = []

    for rows in shared.values():
        for first in range(len(rows)):
            for second in range(first + 1, len(rows)):
                left, right = rows[first], rows[second]
                # Two judgements by the same account are consistency, not agreement, and
                # pooling them here would flatter the number. They are reported apart.
                if left.get("account_id") is not None and left["account_id"] == right.get(
                    "account_id"
                ):
                    continue
                choice_pairs.append(
                    (left.get("choice_arm") or "none", right.get("choice_arm") or "none")
                )
                left_triage = left.get("triage_arm") or {}
                right_triage = right.get("triage_arm") or {}
                for arm in ARMS:
                    if arm in left_triage and arm in right_triage:
                        triage_pairs.append((left_triage[arm], right_triage[arm]))

    return {
        "sets_shared": len(shared),
        "choice": _pooled_kappa(choice_pairs),
        "triage": _pooled_kappa(triage_pairs),
    }


def _pooled_kappa(pairs: list[tuple[str, str]]) -> dict:
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


# «Sin evaluador» and not «cuenta borrada», because `account_id` goes null for two reasons
# and only one of them is a deletion: a comparison stocked from the panel has no evaluator
# until somebody is handed a copy, and calling that data loss reads as an incident.
# `user_id` is SET NULL on deletion, so the two are the same row from here — and «no hay
# quien lo juzgue» is the true statement about both.
def _account_label(row: dict) -> str:
    return row.get("account") or row.get("account_name") or "Sin evaluador"


def _grouped(headers: list[dict], key: str, label_of) -> list[dict]:
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
                "last_at": max(r.get("created_at") or 0 for r in rows),
                **summary,
            }
        )
    return sorted(groups, key=lambda g: (-g["sessions"], g["label"]))


# One point per day, so the panel can say whether the study is still collecting data or
# stopped three weeks ago — which no mean can answer.
def per_day(headers: list[dict]) -> list[dict]:
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


# One row per session, every column the analysis needs, and the two the file version could
# never carry: who evaluated and in which instance. Restricted to the installation's
# administrator, because a per-session export of everybody's judgements is the study's
# raw data and not a feature of the evaluation screen.
def export_csv(headers: list[dict]) -> str:
    columns = [
        "session_id",
        "created_at",
        "workspace",
        "account",
        # The three the analysis groups by, and which no earlier version of this file could
        # carry: who judged it, from which side of the desk, and whether somebody else
        # judged the same three items.
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
        shuffle = row.get("shuffle") or []
        rating = row.get("rating") or {}
        line = {
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
            "choice": row.get("choice") if row.get("choice") is not None else "",
            "choice_arm": row.get("choice_arm") or "",
            "chosen_at": _iso(row.get("chosen_at")),
            "declined": int(bool(row.get("declined_at"))),
            "seconds": row.get("seconds") if row.get("seconds") is not None else "",
            "evaluator_note": row.get("evaluator_note") or "",
            "usability": rating.get("usability", ""),
            "rating_comment": rating.get("comment", ""),
        }
        for index in range(3):
            line[f"position_{index + 1}"] = shuffle[index] if index < len(shuffle) else ""
        for arm in ARMS:
            line[f"triage_{arm}"] = (row.get("triage_arm") or {}).get(arm, "")
            line[f"{arm}_status"] = (row.get("arm_status") or {}).get(arm, "")
            line[f"{arm}_ms"] = (row.get("arm_elapsed_ms") or {}).get(arm, "")
        for name in RATING_SCALES:
            line[name] = rating.get(name, "")
        writer.writerow(csv_safe.row(line))
    return buffer.getvalue()


def _iso(timestamp: float | None) -> str:
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")
