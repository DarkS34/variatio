"""The arithmetic over what teachers answered about each build, for the panel and the CSV.

The blind comparison has `store.py`; this is its twin for the OTHER instrument, the five
Likert statements asked at the foot of every stage of the construction. It reads
`stage_evaluations` into flat headers and then only ever computes over those, so the
aggregates can be pinned against hand-computed values without a database in the way —
exactly as `store.py` does.

Nothing here needs scipy: every statement is the same 1-5 agreement scale, so what the
memoria needs is counts per rung, a mean per statement, a share of agreement and a median.
"""

import csv
import io
from datetime import datetime

from sqlalchemy.orm import Session as DbSession

from server import approvals, csv_safe

from . import stage_instruments, stage_queries

# The rungs of `effort` that leave the artifact usable, which is the reading the panel
# gives beside the raw counts: "de acuerdo" and "totalmente de acuerdo" with "lo podría
# usar tal cual" together are "lo usaría".
USABLE_EFFORT = tuple(range(stage_instruments.AGREE_FROM, stage_instruments.SCALE_MAX + 1))

# The three states of the curation mark, named so a CSV column and a card agree.
CURATION = ("yes", "no", "unknown")


# READ ------------------------------------------------------------------------------------------


def headers(db: DbSession, workspace_id: int | None = None) -> list[dict]:
    """Read the whole population as headers, each carrying its author and its workspace.

    Unanswered rows are INCLUDED: "opened it and never answered" is a datum about whether a
    panel of teachers engages at all, and the aggregates count it apart from a verdict.
    """
    return [
        header(row, user, workspace.slug)
        for row, workspace, user in stage_queries.everything(db, workspace_id)
    ]


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


# AGGREGATES ------------------------------------------------------------------------------------


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
            for artifact in approvals.ARTIFACTS
        ],
    }


def artifact_summary(artifact: str, rows: list[dict]) -> dict:
    """Summarise one stage: how many answered, `overall`, and every statement's rungs."""
    answered = [row for row in rows if row["answered"]]
    overall = [row["overall"] for row in answered]

    questions = [
        _question_summary(question, answered)
        for question in stage_instruments.QUESTIONS.get(artifact, ())
    ]
    # Over the answers ON THE SCALE only: a row from before the scale keeps its raw value
    # in the counts, but "none" was that wording's best rung and reading it as
    # disagreement would pull the share down for a verdict that said the opposite.
    effort = next((q for q in questions if q["key"] == "effort"), None)
    usable = None
    if effort:
        scored = sum(effort["counts"].get(str(value), 0) for value in stage_instruments.SCALE_VALUES)
        if scored:
            usable = round(
                sum(effort["counts"].get(str(value), 0) for value in USABLE_EFFORT) / scored, 3
            )

    instruments: dict[str, int] = {}
    for row in answered:
        instruments[row["instrument"]] = instruments.get(row["instrument"], 0) + 1

    return {
        "artifact": artifact,
        "opened": len(rows),
        "answered": len(answered),
        "overall": {
            "statement": stage_instruments.for_artifact(artifact)["overall"]["statement"],
            "n": len(overall),
            "mean": _mean(overall),
            "counts": _scale_counts(overall),
        },
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


def _question_summary(question: dict, rows: list[dict]) -> dict:
    """Count the answers to one statement over these rows, rung by rung, with their mean."""
    key = question["key"]
    values = [row["answers"].get(key) for row in rows]
    counts = _scale_counts(values)
    return {
        "key": key,
        "axis": question.get("axis") or stage_instruments.AXES.get(key, ""),
        "statement": question["statement"],
        "options": _scale_options(counts),
        "counts": counts,
        "n": sum(counts.values()),
        "mean": _mean(_scores(values)),
    }


def _scale_counts(values: list) -> dict[str, int]:
    """Count answers per rung, every rung present and in order, an earlier wording's after.

    Keyed by the rung as a STRING, like `overall`'s counts, so a JSON reader sees one
    shape for the six scales of a stage. A value the current instrument does not offer —
    an option of a version before the scale — is kept under its raw key rather than
    dropped, because it was answered.
    """
    counts: dict[str, int] = {str(value): 0 for value in stage_instruments.SCALE_VALUES}
    for value in values:
        if value is None:
            continue
        score = stage_instruments.as_score(value)
        key = str(score) if score is not None else str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _scale_options(counts: dict[str, int]) -> list[dict]:
    """Name every rung the counts hold: the scale's own labels, and the raw value otherwise."""
    labels = dict(zip(map(str, stage_instruments.SCALE_VALUES), stage_instruments.SCALE_LABELS))
    return [{"value": value, "label": labels.get(value, value)} for value in counts]


def _scores(values: list) -> list[int]:
    """The answers that are on the scale, as numbers, for a mean."""
    return [s for s in (stage_instruments.as_score(v) for v in values) if s is not None]


def _curation_summary(answered: list[dict]) -> dict:
    """Split the verdicts by whether the person had corrected the artifact first.

    This is the contrast the `curated` column exists for — how the people who corrected the
    artifact rate it against the people who did not — and the third bucket is every row that
    predates the
    question, which is not a "no".
    """
    buckets: dict[str, list[dict]] = {state: [] for state in CURATION}
    for row in answered:
        state = "unknown" if row["curated"] is None else ("yes" if row["curated"] else "no")
        buckets[state].append(row)
    return {
        state: {"n": len(rows), "overall_mean": _mean([r["overall"] for r in rows])}
        for state, rows in buckets.items()
    }


def _median(values: list[float]) -> float | None:
    """Return the median, or None over nothing."""
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[middle], 1)
    return round((ordered[middle - 1] + ordered[middle]) / 2, 1)


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
                    for artifact in approvals.ARTIFACTS
                },
                "curated": sum(1 for row in answered if row["curated"]),
                "last_at": max(row.get("updated_at") or row.get("created_at") or 0 for row in rows),
            }
        )
    return sorted(groups, key=lambda g: (-g["answered"], -g["opened"], g["label"]))


def _mean(values: list[int | float]) -> float | None:
    """Return the mean rounded to two decimals, or None over nothing."""
    return round(sum(values) / len(values), 2) if values else None


def _account_label(row: dict) -> str:
    """Name the evaluator, or "Sin evaluador" — never "cuenta borrada"."""
    return row.get("account") or row.get("account_name") or "Sin evaluador"


# EXPORT ----------------------------------------------------------------------------------------

# One column per axis, in the order asked — the same four keys on the three stages, so a
# spreadsheet reads the same across them. An answer under an earlier wording's key lands
# in `other_answers`, exactly as before.
ANSWER_COLUMNS: tuple[str, ...] = tuple(stage_instruments.AXES)


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


def _iso(timestamp: float | None) -> str:
    """Render a POSIX timestamp as a local ISO string to the second, or as empty."""
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")
