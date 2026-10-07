"""What a subject's students do, week by week, for its teachers («Clase → Actividad»).

Decided 2026-10-07, at the user's request and changing three closed decisions: a subject's
teachers read what its students ask the tutor and which exercises they generate, of the class
and of each student. They never read a conversation or an exercise: this module counts, from
the files, what a message was ABOUT — its date, the kind of reply it got, the concept it stood
on, the prerequisite it was sent back to — and what an exercise WAS — its date, type, level
and concepts. The words of what students ask are the model's, once a teacher asks for them
(`activity_digest`, the tutor's job), in paraphrase and checked by code.

THE WEEK IS THE UNIT: ISO weeks, Monday to Sunday, in UTC like every other day of the system
(`server/daily.py`). The history of a class is its list of weeks, from the first with activity
to the present one, an empty week kept as a gap. A past week is closed — every message and
every exercise carries its date, so its figures do not move — and the present one is open.

WHO COUNTS: the subject's students (`viewer`), active and paused, a paused one marked. A
student removed from the subject is no longer of the class and counts for nothing, though
their files stay. A teacher's own exercises and conversations are not the class's.

The tutor's half is the tutor's to read: `tutor.api.install` sets `TUTOR_READER`, which turns
the conversations into `Message`s, and without it the activity has no tutor block. Every file
is read once and kept by its modification time, so a hundred students' directories cost a
listing per request and a parse per changed file.
"""

import re
import statistics
import threading
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from variatio.core.workspace import Workspace
from variatio.instance import locale
from variatio.instance.knowledge_graph import KnowledgeGraph

from . import daily, generations
from .db import identity
from .db.models import VIEWER, Workspace as WorkspaceRow

WEEK_PATTERN = re.compile(r"\A(\d{4})-W(\d{2})\Z")

# Below these, a pattern is one student's habit and not the class's: a concept asked by fewer
# students is not a finding, nor a share of «give me the solution» over fewer messages.
# Placeholders until the pilot measures them.
MIN_ASKERS = 3
SOLUTION_SHARE = 0.4
MIN_SOLUTION_MESSAGES = 5
MAX_FINDINGS = 5
# The fewest messages of the subject's own a week needs before its words are worth a model.
DIGEST_MIN_MESSAGES = 10


@dataclass(frozen=True)
class Student:
    """One student of the subject, as the class list names them."""

    id: int
    name: str
    username: str
    disabled: bool


@dataclass(frozen=True)
class Message:
    """One message a student sent the tutor, without its text.

    `kind` is the kind of reply it got (None while unanswered); `on_subject` says whether that
    kind works on the subject (a greeting, an administrative question, a refusal do not);
    `concept` is the one the student chose, else the one the reply stood on; `sent_back` the
    prerequisite the reply sent the student to review.
    """

    user_id: int
    conversation: str
    turn: int
    at: datetime
    kind: str | None
    on_subject: bool
    concept: str | None
    sent_back: str | None


@dataclass(frozen=True)
class TutorReading:
    """The students' messages, and which of their exercises they took to the tutor."""

    messages: list[Message]
    taken: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Exercise:
    """One exercise a student generated, without its statement."""

    id: str
    user_id: int
    at: datetime
    item_type: str
    level: str | None
    concepts: tuple[str, ...]


# The tutor's reader of its conversations, set by `tutor.api.install`; None without a tutor.
TUTOR_READER: Callable[[Workspace, list[int]], TutorReading] | None = None


# THE WEEK ------------------------------------------------------------------------------


def week_of(moment: datetime | date) -> str:
    """Return the ISO week a moment falls in, as `2026-W41`."""
    year, week, _ = moment.isocalendar()
    return f"{year}-W{week:02d}"


def parse_week(text: str) -> str:
    """Return a week as this module writes it, or raise ValueError for anything else."""
    match = WEEK_PATTERN.match(text or "")
    if match is None:
        raise ValueError(f"«{text}» no es una semana")
    year, week = int(match.group(1)), int(match.group(2))
    date.fromisocalendar(year, week, 1)
    return f"{year}-W{week:02d}"


def monday(week: str) -> date:
    """Return the first day of a week."""
    match = WEEK_PATTERN.match(week)
    if match is None:
        raise ValueError(f"«{week}» no es una semana")
    return date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)


def current_week(now: datetime | None = None) -> str:
    """Return the week the present moment falls in."""
    return week_of(now or daily.now())


def previous_week(week: str) -> str:
    """Return the week before this one."""
    return week_of(monday(week) - timedelta(days=7))


def weeks_from(first: str, last: str) -> list[str]:
    """Return every week from `last` back to `first`, the newest first."""
    out, cursor, stop = [], monday(last), monday(first)
    while cursor >= stop:
        out.append(week_of(cursor))
        cursor -= timedelta(days=7)
    return out


# WHO AND WHAT ---------------------------------------------------------------------------


def students_of(session: Session, workspace: WorkspaceRow) -> list[Student]:
    """Return the subject's students, active and paused, by name."""
    rows = identity.members_of(session, workspace.id, include_disabled=True)
    found = [
        Student(user.id, user.name or user.username, user.username, row.disabled_at is not None)
        for row, user in rows
        if row.role == VIEWER
    ]
    return sorted(found, key=lambda student: (student.name.lower(), student.username))


def exercises(ws: Workspace, user_ids: list[int]) -> list[Exercise]:
    """Return every exercise these accounts generated in the subject."""
    field_name, _ = locale.difficulty(ws)
    found: list[Exercise] = []
    for user_id in user_ids:
        directory = generations.author_dir(ws, user_id)
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            summary = cached(path, lambda record, u=user_id: _exercise(record, u, field_name))
            if summary is not None:
                found.append(summary)
    return found


def _exercise(record: dict, user_id: int, level_field: str) -> Exercise | None:
    """Summarise one exercise's record: when, of which type and level, about what."""
    at = moment_of(record.get("created_at"))
    if at is None:
        return None
    level = generations.item_of(record).get(level_field)
    if level in (None, ""):
        level = ((record.get("commission") or {}).get("fixed") or {}).get(level_field)
    return Exercise(
        id=str(record.get("id") or ""),
        user_id=user_id,
        at=at,
        item_type=generations.item_type_of(record),
        level=str(level) if level not in (None, "") else None,
        concepts=tuple(generations.concepts_of(record)),
    )


def tutor_reading(ws: Workspace, user_ids: list[int]) -> TutorReading | None:
    """Return the students' messages to the tutor, or None where the tutor is not installed."""
    if TUTOR_READER is None:
        return None
    return TUTOR_READER(ws, user_ids)


_cache: dict[Path, tuple[int, int, object]] = {}
_cache_lock = threading.Lock()


def cached(
    path: Path,
    summarise: Callable[[dict], object],
    reader: Callable[[Path], dict | None] = generations.read,
) -> object:
    """Return a file's summary, reading and parsing it again only when its time or size changed.

    The tutor's reader goes through it too, with its own `reader`: one cache for every file a
    week reads.
    """
    try:
        stat = path.stat()
    except OSError:
        return None
    key = (stat.st_mtime_ns, stat.st_size)
    with _cache_lock:
        held = _cache.get(path)
    if held is not None and held[:2] == key:
        return held[2]
    record = reader(path)
    summary = summarise(record) if record is not None else None
    with _cache_lock:
        _cache[path] = (*key, summary)
    return summary


def moment_of(value: object) -> datetime | None:
    """Read an ISO moment a record carries, in UTC, or None."""
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


# THE HISTORY ----------------------------------------------------------------------------


@dataclass
class _Scope:
    """What one reading counts: the class's students, or one of them."""

    students: list[Student]
    student: Student | None
    messages: list[Message] = field(default_factory=list)
    exercises: list[Exercise] = field(default_factory=list)
    taken: frozenset[str] = frozenset()
    tutor: bool = True

    @property
    def ids(self) -> set[int]:
        """Return the accounts this reading counts."""
        return {self.student.id} if self.student else {s.id for s in self.students}


def read_scope(ws: Workspace, students: list[Student], student: Student | None = None) -> _Scope:
    """Read every message and exercise of the class, kept whole: a scope narrows on use."""
    ids = [s.id for s in students]
    reading = tutor_reading(ws, ids)
    return _Scope(
        students=students,
        student=student,
        messages=list(reading.messages) if reading else [],
        exercises=exercises(ws, ids),
        taken=reading.taken if reading else frozenset(),
        tutor=reading is not None,
    )


def history(scope: _Scope, digests: set[str], now: datetime | None = None) -> dict:
    """Return the strip of weeks: every week with its figures, the newest first.

    It starts at the first week anybody of the class did something, so a class's history
    opens where it began; a student's strip is the class's weeks, with that student's figures.
    """
    present = current_week(now)
    weeks = [week_of(m.at) for m in scope.messages] + [week_of(e.at) for e in scope.exercises]
    first = min(weeks) if weeks else present
    mine = scope.ids
    messages = Counter(week_of(m.at) for m in scope.messages if m.user_id in mine)
    made = Counter(week_of(e.at) for e in scope.exercises if e.user_id in mine)
    active: dict[str, set[int]] = defaultdict(set)
    for m in scope.messages:
        if m.user_id in mine:
            active[week_of(m.at)].add(m.user_id)
    for e in scope.exercises:
        if e.user_id in mine:
            active[week_of(e.at)].add(e.user_id)
    return {
        "current": present,
        "weeks": [
            {
                "week": week,
                "start": monday(week).isoformat(),
                "messages": messages.get(week, 0),
                "exercises": made.get(week, 0),
                "active": len(active.get(week, ())),
                "digest": week in digests,
            }
            for week in weeks_from(min(first, present), present)
        ],
    }


# ONE WEEK -------------------------------------------------------------------------------


def week(
    scope: _Scope,
    week_key: str,
    graph: KnowledgeGraph | None,
    progress: list[str] | None = None,
    digest: dict | None = None,
    now: datetime | None = None,
) -> dict:
    """Return one week of the class, or of one student: figures, findings and the digest."""
    start = monday(week_key)
    present = current_week(now)
    order = _syllabus_order(graph)
    unit_of = graph.concept_domain if graph else {}
    mine = scope.ids
    messages = [m for m in scope.messages if m.user_id in mine and week_of(m.at) == week_key]
    made = [e for e in scope.exercises if e.user_id in mine and week_of(e.at) == week_key]
    class_ids = {s.id for s in scope.students}
    class_messages = [
        m for m in scope.messages if m.user_id in class_ids and week_of(m.at) == week_key
    ]

    tutor = _tutor_block(messages, order, unit_of, start) if scope.tutor else None
    exercises_block = _exercises_block(made, scope.taken, order, unit_of, graph, progress, start)
    on_subject = sum(1 for m in class_messages if m.on_subject)
    answer = {
        "week": week_key,
        "start": start.isoformat(),
        "closed": week_key < present,
        "scope": "student" if scope.student else "class",
        "student": _student_view(scope.student) if scope.student else None,
        "class_size": len(scope.students),
        "tutor": tutor,
        "exercises": exercises_block,
        "digest": _digest_view(digest, class_messages, class_ids, scope.student),
        "digest_ready": on_subject >= DIGEST_MIN_MESSAGES,
    }
    if scope.student:
        answer["median"] = _medians(scope, week_key)
        answer["findings"] = _student_findings(messages, made, week_key < present, unit_of)
    else:
        answer["students"] = _students_rows(scope, week_key, start)
        answer["findings"] = _class_findings(
            scope, messages, made, exercises_block, graph, progress, week_key, week_key < present
        )
    return answer


def _tutor_block(messages: list[Message], order: dict[str, int], unit_of: dict, start: date) -> dict:
    """Count a week's messages: by kind of reply, by concept and by prerequisite sent back to."""
    by_concept: dict[str, list[Message]] = defaultdict(list)
    for m in messages:
        if m.on_subject and m.concept:
            by_concept[m.concept].append(m)
    sent: dict[tuple[str, str], set[int]] = defaultdict(set)
    sent_times: Counter = Counter()
    for m in messages:
        if m.sent_back and m.concept:
            sent[(m.concept, m.sent_back)].add(m.user_id)
            sent_times[(m.concept, m.sent_back)] += 1
    return {
        "messages": len(messages),
        "students": len({m.user_id for m in messages}),
        "by_kind": dict(Counter(m.kind for m in messages if m.kind)),
        "by_concept": [
            {
                "concept": concept,
                "unit": unit_of.get(concept),
                "messages": len(group),
                "students": len({m.user_id for m in group}),
            }
            for concept, group in sorted(by_concept.items(), key=lambda pair: _rank(order, pair[0]))
        ],
        "sent_back": [
            {
                "concept": concept,
                "prerequisite": prerequisite,
                "times": sent_times[(concept, prerequisite)],
                "students": len(people),
            }
            for (concept, prerequisite), people in sorted(
                sent.items(), key=lambda pair: (-sent_times[pair[0]], pair[0])
            )
        ][:5],
        "per_day": _per_day((m.at for m in messages), start),
    }


def _exercises_block(
    made: list[Exercise],
    taken: frozenset[str],
    order: dict[str, int],
    unit_of: dict,
    graph: KnowledgeGraph | None,
    progress: list[str] | None,
    start: date,
) -> dict:
    """Count a week's exercises: by type and level, by concept and by unit of the syllabus."""
    by_type: dict[str, Counter] = defaultdict(Counter)
    for e in made:
        by_type[e.item_type][e.level or ""] += 1
    by_concept: dict[str, list[Exercise]] = defaultdict(list)
    for e in made:
        for concept in e.concepts:
            by_concept[concept].append(e)
    per_unit: Counter = Counter()
    for e in made:
        for unit in {unit_of.get(c) for c in e.concepts if unit_of.get(c)}:
            per_unit[unit] += 1
    covered = set(progress or [])
    units = graph.domains if graph else sorted(per_unit)
    return {
        "count": len(made),
        "students": len({e.user_id for e in made}),
        "by_type": [
            {"type": item_type, "count": sum(levels.values()), "levels": dict(levels)}
            for item_type, levels in sorted(by_type.items(), key=lambda pair: -sum(pair[1].values()))
        ],
        "by_concept": [
            {
                "concept": concept,
                "unit": unit_of.get(concept),
                "count": len(group),
                "students": len({e.user_id for e in group}),
            }
            for concept, group in sorted(by_concept.items(), key=lambda pair: _rank(order, pair[0]))
        ],
        "by_unit": [
            {
                "unit": unit,
                "count": per_unit.get(unit, 0),
                "covered": (
                    any(c in covered for c in graph.concepts_by_domains.get(unit, []))
                    if graph and covered
                    else None
                ),
            }
            for unit in units
        ],
        "to_tutor": sum(1 for e in made if e.id in taken),
        "per_day": _per_day((e.at for e in made), start),
    }


def _students_rows(scope: _Scope, week_key: str, start: date) -> list[dict]:
    """One row per student of the class: what they did this week, day by day, least first."""
    rows = []
    for student in scope.students:
        sent = [m for m in scope.messages if m.user_id == student.id and week_of(m.at) == week_key]
        made = [e for e in scope.exercises if e.user_id == student.id and week_of(e.at) == week_key]
        days = [a + b for a, b in zip(_per_day((m.at for m in sent), start), _per_day((e.at for e in made), start))]
        rows.append({**_student_view(student), "messages": len(sent), "exercises": len(made), "days": days})
    rows.sort(key=lambda row: (row["messages"] + row["exercises"], row["name"].lower()))
    return rows


def _medians(scope: _Scope, week_key: str) -> dict:
    """Return the class's median of messages and of exercises this week, the idle included."""
    sent = Counter(m.user_id for m in scope.messages if week_of(m.at) == week_key)
    made = Counter(e.user_id for e in scope.exercises if week_of(e.at) == week_key)
    ids = [s.id for s in scope.students if not s.disabled] or [s.id for s in scope.students]
    if not ids:
        return {"messages": 0, "exercises": 0}
    return {
        "messages": statistics.median(sent.get(i, 0) for i in ids),
        "exercises": statistics.median(made.get(i, 0) for i in ids),
    }


# WHAT MATTERS ----------------------------------------------------------------------------


def _class_findings(
    scope: _Scope,
    messages: list[Message],
    made: list[Exercise],
    exercises_block: dict,
    graph: KnowledgeGraph | None,
    progress: list[str] | None,
    week_key: str,
    closed: bool,
) -> list[dict]:
    """Turn a week of the class into what a teacher should read first, at most five.

    In this order: where the class gets stuck (a concept many ask about, and the prerequisite
    the tutor sends them back to), where they ask for the solution, a unit already covered
    that nobody practised, who did nothing, and how many were active against the week before.
    """
    found: list[dict] = []
    askers: dict[str, set[int]] = defaultdict(set)
    for m in messages:
        if m.on_subject and m.concept:
            askers[m.concept].add(m.user_id)
    active = [s for s in scope.students if not s.disabled]
    for concept, people in sorted(askers.items(), key=lambda pair: -len(pair[1]))[:2]:
        if len(people) < MIN_ASKERS:
            break
        sent = Counter(m.sent_back for m in messages if m.concept == concept and m.sent_back)
        prerequisite, _ = sent.most_common(1)[0] if sent else (None, 0)
        found.append(
            {
                "kind": "asked",
                "concept": concept,
                "students": len(people),
                "of": len(active),
                "prerequisite": prerequisite,
                "sent_back": len(
                    {m.user_id for m in messages if m.concept == concept and m.sent_back == prerequisite}
                )
                if prerequisite
                else 0,
            }
        )
    by_concept: dict[str, list[Message]] = defaultdict(list)
    for m in messages:
        if m.on_subject and m.concept:
            by_concept[m.concept].append(m)
    for concept, group in sorted(by_concept.items(), key=lambda pair: -len(pair[1])):
        solutions = sum(1 for m in group if m.kind == "solution")
        if len(group) >= MIN_SOLUTION_MESSAGES and solutions / len(group) >= SOLUTION_SHARE:
            found.append({"kind": "solutions", "concept": concept, "solution": solutions, "messages": len(group)})
            break
    if progress:
        untouched = [row["unit"] for row in exercises_block["by_unit"] if row["covered"] and row["count"] == 0]
        if untouched:
            found.append({"kind": "unpractised", "units": untouched[:3], "more": max(0, len(untouched) - 3)})
    doing = {m.user_id for m in messages} | {e.user_id for e in made}
    idle = [s for s in active if s.id not in doing]
    if active and idle:
        found.append({"kind": "idle", "students": len(idle), "of": len(active), "open": not closed})
    before = previous_week(week_key)
    previously = {m.user_id for m in scope.messages if week_of(m.at) == before} | {
        e.user_id for e in scope.exercises if week_of(e.at) == before
    }
    previously &= {s.id for s in scope.students}
    now_active = len(doing & {s.id for s in scope.students})
    if previously and now_active != len(previously):
        found.append({"kind": "trend", "active": now_active, "previous": len(previously), "open": not closed})
    return found[:MAX_FINDINGS]


def _student_findings(
    messages: list[Message], made: list[Exercise], closed: bool, unit_of: dict
) -> list[dict]:
    """Turn a week of one student into what a teacher should read first about them.

    What they asked most, where the tutor sent them back to, what they practised most. The
    class's median is no finding: every figure of their week already stands beside it.
    """
    if not messages and not made:
        return [{"kind": "quiet", "open": not closed}]
    found: list[dict] = []
    topics = Counter(m.concept for m in messages if m.on_subject and m.concept)
    if topics:
        concept, count = topics.most_common(1)[0]
        found.append({"kind": "topic", "concept": concept, "messages": count})
    sent = Counter(m.sent_back for m in messages if m.sent_back)
    if sent:
        prerequisite, times = sent.most_common(1)[0]
        found.append({"kind": "reviewed", "prerequisite": prerequisite, "times": times})
    units = Counter(unit_of.get(c) for e in made for c in e.concepts if unit_of.get(c))
    if units:
        unit, count = units.most_common(1)[0]
        found.append({"kind": "practised", "unit": unit, "exercises": count})
    return found[:MAX_FINDINGS]


# THE DIGEST ----------------------------------------------------------------------------


def digest_path(ws: Workspace, week_key: str) -> Path:
    """Return where the digest of one week of the subject is kept."""
    return ws.root / "analytics" / "digest" / f"{week_key}.json"


def digested_weeks(ws: Workspace) -> set[str]:
    """Return the weeks of the subject that have a digest written."""
    directory = ws.root / "analytics" / "digest"
    if not directory.is_dir():
        return set()
    return {path.stem for path in directory.glob("*.json") if WEEK_PATTERN.match(path.stem)}


def _digest_view(
    digest: dict | None, class_messages: list[Message], class_ids: set[int], student: Student | None
) -> dict | None:
    """Render a stored digest for the class, or for one student, counted over who is of the class.

    A theme's figures come from its references, so a student removed since it was written no
    longer counts; for one student, only the themes their messages fall under, with how many
    are theirs.
    """
    if not digest:
        return None
    written = moment_of(digest.get("written_at"))
    concepts = []
    for entry in digest.get("concepts") or []:
        themes = []
        for theme in entry.get("themes") or []:
            refs = [ref for ref in theme.get("refs") or [] if isinstance(ref, list) and len(ref) == 3]
            people = {int(ref[0]) for ref in refs if int(ref[0]) in class_ids}
            counted = [ref for ref in refs if int(ref[0]) in class_ids]
            mine = sum(1 for ref in counted if student and int(ref[0]) == student.id)
            if not counted or (student and not mine):
                continue
            themes.append(
                {
                    "text": str(theme.get("text") or ""),
                    "messages": len(counted),
                    "students": len(people),
                    **({"mine": mine} if student else {}),
                }
            )
        if themes:
            concepts.append({"concept": entry.get("concept"), "unit": entry.get("unit"), "themes": themes})
    new = sum(1 for m in class_messages if m.on_subject and written and m.at > written)
    return {
        "written_at": digest.get("written_at"),
        "messages_seen": digest.get("messages_seen") or 0,
        "new_since": new,
        "concepts": concepts,
    }


# SMALL READINGS ------------------------------------------------------------------------


def _student_view(student: Student) -> dict:
    """Name one student as the screens list them."""
    return {"id": student.id, "name": student.name, "username": student.username, "disabled": student.disabled}


def _per_day(moments, start: date) -> list[int]:
    """Count moments by day of the week starting on `start`, Monday first."""
    days = [0] * 7
    for moment in moments:
        offset = (moment.astimezone(timezone.utc).date() - start).days
        if 0 <= offset < 7:
            days[offset] += 1
    return days


def _syllabus_order(graph: KnowledgeGraph | None) -> dict[str, int]:
    """Return each concept's place in the syllabus."""
    return {concept: index for index, concept in enumerate(graph.all_concepts)} if graph else {}


def _rank(order: dict[str, int], concept: str) -> tuple[int, str]:
    """Sort key for a concept: its place in the syllabus, an unknown one last."""
    return (order.get(concept, len(order)), concept)
