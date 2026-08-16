"""Where evaluation sessions live.

Two files per the plan: `sessions.jsonl` carries one header line per session and is read
whole for the aggregates, while `<id>.json` carries the full trace — the three prompts,
the three raw answers, the exemplars and the timings. Splitting them is what keeps the
listing from loading megabytes of prompt every time it paints a table.

The header fields ARE the columns of the future Postgres block, so migrating is a `for`
over the JSONL, not a redesign.
"""

import csv
import io
import json
import threading
import time
from pathlib import Path

from variant_generator.evaluation import ARMS, EvaluationSession

from . import settings

RATING_SCALES = ("originality", "complexity", "concept_fit", "soundness")
USABILITY_VALUES = ("as_is", "with_edits", "no")

_lock = threading.RLock()


def sessions_path() -> Path:
    return settings.workspace().eval_sessions_dir / "sessions.jsonl"


def trace_path(session_id: str) -> Path:
    return settings.workspace().eval_sessions_dir / f"{session_id}.json"


# WRITE -----------------------------------------------------------------------------------------


def save(session: EvaluationSession) -> None:
    with _lock:
        _write_json(trace_path(session.id), session.to_dict())
        headers = [h for h in _read_headers() if h["id"] != session.id]
        headers.append(_header(session))
        _write_headers(headers)


def record_choice(
    session_id: str, choice: int | None, note: str | None = None
) -> EvaluationSession:
    with _lock:
        session = load(session_id)
        if session is None:
            raise KeyError(session_id)
        if session.decided:
            raise ValueError("already-chosen")
        if choice is not None and choice not in (1, 2, 3):
            raise ValueError("choice must be 1, 2, 3 or null")

        session.choice = choice
        session.choice_arm = session.arm_at(choice) if choice is not None else None
        session.chosen_at = time.time()
        session.evaluator_note = (note or "").strip() or None
        save(session)
        return session


def record_rating(session_id: str, rating: dict) -> EvaluationSession:
    with _lock:
        session = load(session_id)
        if session is None:
            raise KeyError(session_id)
        if not session.decided:
            raise ValueError("not-chosen-yet")

        session.rating = _clean_rating(rating)
        save(session)
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


def load(session_id: str) -> EvaluationSession | None:
    path = trace_path(session_id)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        return EvaluationSession.from_dict(json.load(f))


def listing(limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    headers = sorted(_read_headers(), key=lambda h: h.get("created_at") or 0, reverse=True)
    return headers[offset : offset + limit], len(headers)


# Everything per-arm is counted over DECIDED sessions only, and that is a blinding
# requirement, not a statistical preference: with a session still waiting to be judged,
# "naive: unavailable 1" next to a card that shows no exercise names the card.
def aggregates() -> dict:
    headers = _read_headers()
    decided = [h for h in headers if h.get("chosen_at")]

    preferences = {arm: 0 for arm in ARMS}
    preferences["none"] = 0
    for header in decided:
        preferences[header.get("choice_arm") or "none"] += 1

    status_counts = {arm: {} for arm in ARMS}
    for header in decided:
        for arm, status in (header.get("arm_status") or {}).items():
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
        for header in rows:
            preferences[header.get("choice_arm") or "none"] += 1
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


def export_csv() -> str:
    columns = [
        "session_id",
        "created_at",
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
    for header in sorted(_read_headers(), key=lambda h: h.get("created_at") or 0):
        shuffle = header.get("shuffle") or []
        rating = header.get("rating") or {}
        row = {
            "session_id": header["id"],
            "created_at": _iso(header.get("created_at")),
            "job_id": header.get("job_id") or "",
            "item_type": header.get("item_type") or "",
            "concepts": "|".join(header.get("concepts") or []),
            "curriculum": "|".join(header.get("curriculum") or []),
            "fixed": json.dumps(header.get("fixed") or {}, ensure_ascii=False),
            "instructions": header.get("instructions") or "",
            "seed": header.get("seed"),
            "think": int(bool(header.get("think", True))),
            "choice": header.get("choice") if header.get("choice") is not None else "",
            "choice_arm": header.get("choice_arm") or "",
            "chosen_at": _iso(header.get("chosen_at")),
            "evaluator_note": header.get("evaluator_note") or "",
            "usability": rating.get("usability", ""),
            "rating_comment": rating.get("comment", ""),
        }
        for index in range(3):
            row[f"position_{index + 1}"] = shuffle[index] if index < len(shuffle) else ""
        for arm in ARMS:
            row[f"{arm}_status"] = (header.get("arm_status") or {}).get(arm, "")
            row[f"{arm}_ms"] = (header.get("arm_elapsed_ms") or {}).get(arm, "")
        for name in RATING_SCALES:
            row[name] = rating.get(name, "")
        writer.writerow(row)
    return buffer.getvalue()


def _iso(timestamp: float | None) -> str:
    if not timestamp:
        return ""
    from datetime import datetime

    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


# INTERNALS -------------------------------------------------------------------------------------


def _header(session: EvaluationSession) -> dict:
    return {
        "id": session.id,
        "created_at": session.created_at,
        "job_id": session.job_id,
        "concepts": list(session.concepts),
        "item_type": session.item_type,
        "fixed": dict(session.fixed),
        "curriculum": list(session.curriculum),
        "instructions": session.instructions,
        "seed": session.seed,
        "shuffle": list(session.shuffle),
        "think": session.think,
        "choice": session.choice,
        "choice_arm": session.choice_arm,
        "chosen_at": session.chosen_at,
        "evaluator_note": session.evaluator_note,
        "rating": session.rating,
        "arm_status": {arm: result.status for arm, result in session.arms.items()},
        "arm_elapsed_ms": {arm: result.elapsed_ms for arm, result in session.arms.items()},
    }


def _read_headers() -> list[dict]:
    path = sessions_path()
    if not path.is_file():
        return []
    headers = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                headers.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return headers


def _write_headers(headers: list[dict]) -> None:
    payload = "\n".join(json.dumps(h, ensure_ascii=False) for h in headers)
    _write_text(sessions_path(), payload + "\n" if payload else "")


def _write_json(path: Path, data: dict) -> None:
    _write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
