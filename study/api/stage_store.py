"""The arithmetic over what teachers answered about each build, for the panel and the CSV.

The blind comparison has `store.py`; this is its twin for the OTHER instrument, the five
questions asked at the foot of every stage of the construction. It reads `stage_evaluations`
into flat headers and then only ever computes over those, so the aggregates can be pinned
against hand-computed values without a database in the way — exactly as `store.py` does.

Nothing here needs scipy: the questions are ordinal with three or four rungs and the one
scale is 1-5, so what the memoria needs is counts, shares, a mean and a median.
"""

import csv
import io
from datetime import datetime

from sqlalchemy.orm import Session as DbSession

from server import csv_safe, review

from . import stage_instruments, stage_queries

# The rungs of `effort` that leave the artifact usable, which is the reading the panel
# gives beside the raw counts: «nada» and «algún retoque» together are «lo usaría».
USABLE_EFFORT = ("none", "touch_up")

# The three states of the curation mark, named so a CSV column and a card agree.
CURATION = ("yes", "no", "unknown")


# READ ------------------------------------------------------------------------------------------


def header(row, user=None, workspace_slug: str | None = None) -> dict:
    """Flatten one row into the shape every aggregate and the CSV are written against."""
    updated = row.updated_at.timestamp() if row.updated_at else None
    return {
        "id": row.id,
        "created_at": row.created_at.timestamp() if row.created_at else 0.0,
        "updated_at": updated,
        "opened_at": row.opened_at,
        # Time from the form reaching the person to their last save; None when either end
        # is missing, exactly as `store._seconds` treats a comparison.
        "seconds": _seconds(row.opened_at, updated),
        "workspace": workspace_slug,
        "account_id": row.user_id,
        "account": user.username if user else None,
        "account_name": user.name if user else None,
        "evaluator_profile": user.evaluator_profile if user else None,
        "artifact": row.artifact,
        "artifact_hash": row.artifact_hash,
        "job_id": row.job_id,
        "instrument": row.instrument or "",
        "answers": dict(row.answers or {}),
        "overall": row.overall,
        "note": row.note,
        "curated": row.curated,
        "answered": row.overall is not None,
    }


def _seconds(opened: float | None, ended: float | None) -> float | None:
    """Return the time on task, or None when either end is missing or out of order."""
    if not opened or not ended or ended < opened:
        return None
    return round(ended - opened, 1)


def headers(db: DbSession, workspace_id: int | None = None) -> list[dict]:
    """Read the whole population as headers, each carrying its author and its workspace.

    Unanswered rows are INCLUDED: «lo abrió y no lo contestó» is a datum about whether a
    panel of teachers engages at all, and the aggregates count it apart from a verdict.
    """
    return [
        header(row, user, workspace.slug)
        for row, workspace, user in stage_queries.everything(db, workspace_id)
    ]


# AGGREGATES ------------------------------------------------------------------------------------


def _mean(values: list[int | float]) -> float | None:
    """Return the mean rounded to two decimals, or None over nothing."""
    return round(sum(values) / len(values), 2) if values else None


def _median(values: list[float]) -> float | None:
    """Return the median, or None over nothing."""
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[middle], 1)
    return round((ordered[middle - 1] + ordered[middle]) / 2, 1)


def _question_summary(question: dict, rows: list[dict]) -> dict:
    """Count the answers to one question over these rows, in the instrument's own order.

    The options carry their labels, so the panel can name a rung without a copy of the
    instrument in the browser; a value the current wording no longer offers — an earlier
    version's — is kept under its raw key rather than dropped, because it was answered.
    """
    key = question["key"]
    counts: dict[str, int] = {option["value"]: 0 for option in question.get("options", ())}
    for row in rows:
        value = row["answers"].get(key)
        if value is None:
            continue
        counts[value] = counts.get(value, 0) + 1
    return {
        "key": key,
        "axis": stage_instruments.AXES.get(key, ""),
        "question": question["question"],
        "options": [
            {"value": value, "label": _option_label(question, value)}
            for value in counts
        ],
        "counts": counts,
        "n": sum(counts.values()),
    }


def _option_label(question: dict, value: str) -> str:
    """The wording of one option, or the raw value when this wording does not offer it."""
    for option in question.get("options", ()):
        if option["value"] == value:
            return option["label"]
    return value


def _curation_summary(answered: list[dict]) -> dict:
    """Split the verdicts by whether the person had corrected the artifact first.

    This is the contrast the `curated` column exists for — «cómo lo valoran los que
    curaron y cómo los que no» — and the third bucket is every row that predates the
    question, which is not a «no».
    """
    buckets: dict[str, list[dict]] = {state: [] for state in CURATION}
    for row in answered:
        state = "unknown" if row["curated"] is None else ("yes" if row["curated"] else "no")
        buckets[state].append(row)
    return {
        state: {"n": len(rows), "overall_mean": _mean([r["overall"] for r in rows])}
        for state, rows in buckets.items()
    }


def artifact_summary(artifact: str, rows: list[dict]) -> dict:
    """Summarise one stage: how many answered, the 1-5 scale, and every question's counts."""
    answered = [row for row in rows if row["answered"]]
    overall = [row["overall"] for row in answered]
    overall_counts = {
        str(value): 0
        for value in range(stage_instruments.OVERALL_MIN, stage_instruments.OVERALL_MAX + 1)
    }
    for value in overall:
        overall_counts[str(value)] = overall_counts.get(str(value), 0) + 1

    questions = [
        _question_summary(question, answered)
        for question in stage_instruments.QUESTIONS.get(artifact, ())
    ]
    effort = next((q for q in questions if q["key"] == "effort"), None)
    usable = None
    if effort and effort["n"]:
        usable = round(
            sum(effort["counts"].get(value, 0) for value in USABLE_EFFORT) / effort["n"], 3
        )

    instruments: dict[str, int] = {}
    for row in answered:
        instruments[row["instrument"]] = instruments.get(row["instrument"], 0) + 1

    return {
        "artifact": artifact,
        "opened": len(rows),
        "answered": len(answered),
        "overall": {"n": len(overall), "mean": _mean(overall), "counts": overall_counts},
        "questions": questions,
        # The one reading the panel gives beside the raw effort counts.
        "usable": usable,
        "curation": _curation_summary(answered),
        "seconds": {
            "n": len([r for r in answered if r["seconds"] is not None]),
            "median": _median([r["seconds"] for r in answered if r["seconds"] is not None]),
        },
        # Which wording each verdict was given under, so nothing is pooled by accident.
        "instruments": instruments,
        "notes": sum(1 for row in answered if row["note"]),
    }


def aggregates(headers: list[dict]) -> dict:
    """Summarise a population: the totals, and one summary per stage of the chain."""
    answered = [row for row in headers if row["answered"]]
    return {
        "rows": len(headers),
        "answered": len(answered),
        "opened_only": len(headers) - len(answered),
        "overall_mean": _mean([row["overall"] for row in answered]),
        "by_artifact": [
            artifact_summary(artifact, [row for row in headers if row["artifact"] == artifact])
            for artifact in review.ARTIFACTS
        ],
    }


def _account_label(row: dict) -> str:
    """Name the evaluator, or «Sin evaluador» — never «cuenta borrada»."""
    return row.get("account") or row.get("account_name") or "Sin evaluador"


def by_account(headers: list[dict]) -> list[dict]:
    """Group by evaluator: how many forms each one opened, answered, and how they judged.

    `answered` per artifact is what says whether somebody went through the whole chain or
    stopped at the first step, which is the one thing a total cannot say.
    """
    buckets: dict[object, list[dict]] = {}
    for row in headers:
        buckets.setdefault(row.get("account_id"), []).append(row)

    groups = []
    for account_id, rows in buckets.items():
        answered = [row for row in rows if row["answered"]]
        groups.append(
            {
                "key": account_id if account_id is not None else "",
                "label": _account_label(rows[0]),
                "name": rows[0].get("account_name"),
                "evaluator_profile": rows[0].get("evaluator_profile"),
                "opened": len(rows),
                "answered": len(answered),
                "overall_mean": _mean([row["overall"] for row in answered]),
                "per_artifact": {
                    artifact: sum(1 for row in answered if row["artifact"] == artifact)
                    for artifact in review.ARTIFACTS
                },
                "curated": sum(1 for row in answered if row["curated"]),
                "last_at": max(row.get("updated_at") or row.get("created_at") or 0 for row in rows),
            }
        )
    return sorted(groups, key=lambda g: (-g["answered"], -g["opened"], g["label"]))


# EXPORT ----------------------------------------------------------------------------------------

# One column per question key the instrument has ever asked, in the order asked, so a
# spreadsheet reads the same across the three stages: a key a stage does not ask is blank.
ANSWER_COLUMNS: tuple[str, ...] = tuple(stage_instruments.AXES)


def _export_row(row: dict) -> dict:
    """Build one line of the export."""
    curated = row.get("curated")
    line = {
        "id": row["id"],
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
        "opened_at": _iso(row.get("opened_at")),
        "seconds": row.get("seconds") if row.get("seconds") is not None else "",
        "workspace": row.get("workspace") or "",
        "account": row.get("account") or "",
        "evaluator_profile": row.get("evaluator_profile") or "",
        "artifact": row.get("artifact") or "",
        "artifact_hash": row.get("artifact_hash") or "",
        "job_id": row.get("job_id") or "",
        "instrument": row.get("instrument") or "",
        "answered": int(bool(row.get("answered"))),
        "curated": "" if curated is None else int(bool(curated)),
        "overall": row.get("overall") if row.get("overall") is not None else "",
    }
    answers = row.get("answers") or {}
    for key in ANSWER_COLUMNS:
        line[key] = answers.get(key, "")
    # An answer under a key the current instrument does not know is not thrown away: it
    # was given under an earlier wording, and the export is the one place it survives.
    extra = {key: value for key, value in answers.items() if key not in ANSWER_COLUMNS}
    line["other_answers"] = "|".join(f"{key}={value}" for key, value in sorted(extra.items()))
    line["note"] = row.get("note") or ""
    return line


def export_csv(headers: list[dict]) -> str:
    """Render the forms' raw data: one row per (person, build, stage), oldest first."""
    columns = [
        "id",
        "created_at",
        "updated_at",
        "opened_at",
        "seconds",
        "workspace",
        "account",
        "evaluator_profile",
        "artifact",
        "artifact_hash",
        "job_id",
        "instrument",
        "answered",
        "curated",
        "overall",
        *ANSWER_COLUMNS,
        "other_answers",
        "note",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in sorted(headers, key=lambda h: h.get("created_at") or 0):
        writer.writerow(csv_safe.row(_export_row(row)))
    return buffer.getvalue()


def _iso(timestamp: float | None) -> str:
    """Render a POSIX timestamp as a local ISO string to the second, or as empty."""
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")
