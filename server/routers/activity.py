"""A subject's activity, week by week, for its teachers: «Clase → Actividad».

Declares `auth.EDIT`: what the students of a subject do is its teachers' to read, and never a
student's — not even their own (decided 2026-10-07). What it answers is counted by code from
the files (`server/activity.py`): when, about what, of which kind and level, never a message
or a statement; the words of what the class asks are the weekly digest's, written by the
model when a teacher asks for it here, and checked by code before anybody reads them.

A week travels as `2026-W41`; a future week does not exist yet. `?student=<id>` narrows a
reading to one student of the subject, active or paused; anybody else is the same 404 as an
id that names nobody.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.orm import Session as DbSession

from variatio.core import inference

from .. import activity, auth, curriculum, features, singletons
from ..editors import kg_edit
from ..editors.kg_edit import KGError

router = APIRouter(prefix="/api/activity", tags=["activity"], dependencies=[auth.EDIT])

# The tutor's job that writes a week's digest (`tutor/api/digest.py`).
DIGEST_KIND = "activity_digest"
DIGEST_BUSY = "digest_busy"


@router.get("/weeks")
def weeks(
    student: int | None = Query(None),
    access: auth.Access = auth.EDIT,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Answer the class's weeks, the newest first, with their figures, and who is in the class."""
    students = activity.students_of(db, access.workspace)
    scope = activity.read_scope(access.ws, students, _chosen(students, student))
    return {
        **activity.history(scope, activity.digested_weeks(access.ws)),
        "students": [_named(s) for s in students],
        "tutor": scope.tutor,
    }


@router.get("/weeks/{week}")
def week(
    week: str,
    student: int | None = Query(None),
    access: auth.Access = auth.EDIT,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Answer one week of the class, or of one student: figures, findings and the digest."""
    key = _week(week)
    students = activity.students_of(db, access.workspace)
    scope = activity.read_scope(access.ws, students, _chosen(students, student))
    graph = _graph(access)
    progress = curriculum.load(access.ws, graph)["concepts"] if graph else None
    answer = activity.week(scope, key, graph, progress, _digest(access, key))
    answer["tutor_offered"] = features.offered_to_students(db, access.workspace)
    answer["digest_running"] = _live_digest(access.ws.slug, key) is not None
    return answer


@router.post("/weeks/{week}/digest", status_code=201)
def write_digest(
    week: str, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)
) -> dict:
    """Queue the digest of one week: what the class asked the tutor, in a few themes per concept.

    Only with enough messages about the subject to sum up, one at a time per week, and on the
    engine the installation has; a closed week's digest may be written again (the screen
    offers it quietly, for one that came out wrong).
    """
    if activity.TUTOR_READER is None or DIGEST_KIND not in singletons.runner.handlers:
        raise HTTPException(404, "El tutor no está instalado.")
    key = _week(week)
    students = activity.students_of(db, access.workspace)
    scope = activity.read_scope(access.ws, students)
    about = sum(1 for m in scope.messages if m.on_subject and activity.week_of(m.at) == key)
    if about < activity.DIGEST_MIN_MESSAGES:
        raise HTTPException(
            422,
            f"Esa semana hay {about} mensaje(s) sobre la asignatura: hacen falta al menos "
            f"{activity.DIGEST_MIN_MESSAGES} para resumirlos.",
        )
    if _live_digest(access.ws.slug, key) is not None:
        raise HTTPException(
            409,
            "La síntesis de esa semana ya se está escribiendo.",
            headers={"X-Error-Code": DIGEST_BUSY},
        )
    if not inference.is_available():
        raise HTTPException(
            503,
            f"No hay conexión con el motor de inferencia '{inference.engine_name()}'.",
        )
    job = singletons.runner.submit(
        DIGEST_KIND,
        {"week": key},
        workspace=access.ws.slug,
        user_id=access.user.id,
        user_name=access.user.name,
    )
    logger.info(
        "[asignatura] «{}» pidió la síntesis de la semana {} de «{}»",
        access.user.username,
        key,
        access.ws.slug,
    )
    return {
        "job": job.to_dict(),
        "since": singletons.bus.last_seq,
        "queue_position": singletons.runner.queue_position(job.id),
    }


def _week(text: str) -> str:
    """Return the week a path names, or 404 for one that is malformed or has not come yet."""
    try:
        key = activity.parse_week(text)
    except ValueError:
        raise HTTPException(404, f"«{text}» no es una semana.") from None
    if key > activity.current_week():
        raise HTTPException(404, "Esa semana todavía no ha llegado.")
    return key


def _chosen(students: list[activity.Student], student: int | None) -> activity.Student | None:
    """Return the student a reading narrows to, or 404 for an id that is not of the class."""
    if student is None:
        return None
    found = next((s for s in students if s.id == student), None)
    if found is None:
        raise HTTPException(404, "Ese alumno no está en la asignatura.")
    return found


def _named(student: activity.Student) -> dict:
    """Name a student for the screen's picker."""
    return {
        "id": student.id,
        "name": student.name,
        "username": student.username,
        "disabled": student.disabled,
    }


def _graph(access: auth.Access):
    """Return the subject's graph, or None while it has none."""
    try:
        return kg_edit.load_graph(access.ws)
    except KGError:
        return None


def _digest(access: auth.Access, key: str) -> dict | None:
    """Read a week's stored digest, or None when none was written or it cannot be read."""
    path = activity.digest_path(access.ws, key)
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        logger.warning(f"[asignatura] Se salta una síntesis ilegible '{path}'")
        return None
    return data if isinstance(data, dict) else None


def _live_digest(slug: str, key: str):
    """Return the digest job of this week of this subject that is queued or running, if any."""
    live = [*singletons.runner.running(slug), *singletons.runner.pending(slug)]
    return next(
        (job for job in live if job.kind == DIGEST_KIND and job.params.get("week") == key),
        None,
    )
