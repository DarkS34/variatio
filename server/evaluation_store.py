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
import time
from datetime import datetime

from sqlalchemy.orm import Session as DbSession

from study import ARMS, EvaluationSession

from .db import study
from .db.models import EvalSession

RATING_SCALES = ("originality", "complexity", "concept_fit", "soundness")
USABILITY_VALUES = ("as_is", "with_edits", "no")


# WRITE -----------------------------------------------------------------------------------------


def save(
    db: DbSession, workspace_id: int, user_id: int | None, session: EvaluationSession
) -> EvalSession:
    return study.upsert_evaluation(db, session.id, workspace_id, user_id, session.to_dict())


def load(db: DbSession, session_id: str) -> EvaluationSession | None:
    row = study.get_evaluation(db, session_id)
    if row is None:
        return None
    return EvaluationSession.from_dict(row.trace)


def record_choice(
    db: DbSession, row: EvalSession, choice: int | None, note: str | None = None
) -> EvaluationSession:
    session = EvaluationSession.from_dict(row.trace)
    if session.decided:
        raise ValueError("already-chosen")
    if choice is not None and choice not in (1, 2, 3):
        raise ValueError("choice must be 1, 2, 3 or null")

    session.choice = choice
    session.choice_arm = session.arm_at(choice) if choice is not None else None
    session.chosen_at = time.time()
    session.evaluator_note = (note or "").strip() or None
    study.upsert_evaluation(db, session.id, row.workspace_id, row.user_id, session.to_dict())
    return session


def record_rating(db: DbSession, row: EvalSession, rating: dict) -> EvaluationSession:
    session = EvaluationSession.from_dict(row.trace)
    if not session.decided:
        raise ValueError("not-chosen-yet")

    session.rating = _clean_rating(rating)
    study.upsert_evaluation(db, session.id, row.workspace_id, row.user_id, session.to_dict())
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
    return {
        "id": row.id,
        "created_at": row.created_at.timestamp() if row.created_at else 0.0,
        "job_id": row.job_id,
        "concepts": list(row.concepts or []),
        "item_type": row.item_type or "",
        "fixed": dict(row.fixed or {}),
        "curriculum": list(row.curriculum or []),
        "instructions": row.instructions or "",
        "seed": row.seed,
        "shuffle": list(row.shuffle or []),
        "think": bool(row.think),
        "choice": row.choice,
        "choice_arm": row.choice_arm,
        "chosen_at": row.chosen_at,
        "evaluator_note": row.evaluator_note,
        "rating": row.rating,
        "arm_status": dict(row.arm_status or {}),
        "arm_elapsed_ms": dict(row.arm_elapsed_ms or {}),
        "account_id": row.user_id,
        "account": (user.username if user is not None else None),
        "account_name": (user.name if user is not None else None),
        "workspace": workspace_slug,
    }


def listing(
    db: DbSession,
    workspace_id: int,
    author: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    rows, total = study.list_evaluations(
        db, workspace_id=workspace_id, author=author, limit=limit, offset=offset
    )
    return [header(row) for row in rows], total


# AGGREGATES ------------------------------------------------------------------------------------


# Everything per-arm is counted over DECIDED sessions only, and that is a blinding
# requirement, not a statistical preference: with a session still waiting to be judged,
# "naive: unavailable 1" next to a card that shows no exercise names the card.
def aggregates(headers: list[dict]) -> dict:
    decided = [h for h in headers if h.get("chosen_at")]

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
        "rated": sum(1 for h in headers if h.get("rating")),
        "preferences": preferences,
        "arm_status": status_counts,
        "rubric": _rubric_summary([h["rating"] for h in headers if h.get("rating")]),
        "think": _think_breakdown(decided),
        "elapsed_ms": _mean_elapsed(decided),
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


def _account_label(row: dict) -> str:
    return row.get("account") or row.get("account_name") or "cuenta borrada"


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
        "choice",
        "choice_arm",
        "chosen_at",
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
            "evaluator_note": row.get("evaluator_note") or "",
            "usability": rating.get("usability", ""),
            "rating_comment": rating.get("comment", ""),
        }
        for index in range(3):
            line[f"position_{index + 1}"] = shuffle[index] if index < len(shuffle) else ""
        for arm in ARMS:
            line[f"{arm}_status"] = (row.get("arm_status") or {}).get(arm, "")
            line[f"{arm}_ms"] = (row.get("arm_elapsed_ms") or {}).get(arm, "")
        for name in RATING_SCALES:
            line[name] = rating.get(name, "")
        writer.writerow(line)
    return buffer.getvalue()


def _iso(timestamp: float | None) -> str:
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")
