"""The weekly digest's job: what a class asked the tutor in one week, for its teachers.

Registered by `tutor.api.install` and queued by `POST /api/activity/weeks/{week}/digest`, a
teacher's route of the server: a teacher may read the digest of their class whether or not the
tutor is open to their own account, so the job is not behind the tutor's function. It is
background work (class C): the class's own turns go first.

ITS PARAMETERS ARE THE WEEK, AND NOTHING ELSE CROSSES THE STREAM. The messages are read from
their authors' files inside the job, only their steps reach the socket (the repair would quote
the answer it repairs), the log says counts, and what is written — the themes and the
references to the messages they cover, never a message — goes to the subject's
`analytics/digest/<week>.json`, which only the activity's routes read, for teachers.
"""

from collections import defaultdict
from datetime import datetime, timezone

from loguru import logger

from server import activity, deps, installation
from server.db import repository
from server.db.session import session_scope
from server.editors import kg_edit
from server.editors.kg_edit import KGError
from server.jobs.catalogue import Job
from server.jobs.runner import JobControl
from variatio import prompts as prompts_pkg
from variatio.core import json_io, progress
from variatio.instance import locale

from .. import config as tutor_config
from .. import prompts as tutor_prompts_pkg
from ..digest import Asked, summarise
from . import activity as tutor_activity
from . import store
from .jobs import _QuietEmitter

DIGEST = "activity_digest"
FORMAT = 1


def handle_digest(job: Job, control: JobControl) -> dict:
    """Write the digest of `job.params["week"]` for the subject's current students."""
    ws = installation.workspace_for(job.workspace)
    week = activity.parse_week(str(job.params.get("week") or ""))
    with session_scope() as session:
        workspace = repository.get_workspace(session, job.workspace)
        if workspace is None:
            raise ValueError("La asignatura ya no existe.")
        students = activity.students_of(session, workspace)
    names = [part for s in students for part in (s.name, s.username)]

    quiet = progress.set_emitter(_QuietEmitter(control))
    try:
        deps.require_inference()
        language = locale.prompt_language(ws)
        tutor_prompts = tutor_prompts_pkg.of(language)
        prompts = prompts_pkg.of(language)
        try:
            unit_of = kg_edit.load_graph(ws).concept_domain
        except KGError:
            unit_of = {}
        groups = _groups(ws, week, [s.id for s in students])
        concepts = []
        with progress.step("activity_digest", "Summing up the week", len(groups)) as handle:
            for index, (concept, asked) in enumerate(groups, 1):
                progress.checkpoint()
                handle.start(index)
                themes = summarise(
                    concept,
                    unit_of.get(concept),
                    asked,
                    names=names,
                    model=tutor_config.DIGEST_MODEL,
                    think=tutor_config.THINK_DIGEST,
                    tutor_prompts=tutor_prompts,
                    prompts=prompts,
                )
                if themes:
                    concepts.append({"concept": concept, "unit": unit_of.get(concept), "themes": themes})
                handle.tick(index)
    finally:
        progress.reset_emitter(quiet)

    json_io.write_json(
        activity.digest_path(ws, week),
        {
            "format": FORMAT,
            "week": week,
            "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "messages_seen": sum(len(asked) for _, asked in groups),
            "concepts": concepts,
        },
    )
    themes = sum(len(entry["themes"]) for entry in concepts)
    logger.info(
        f"[tutor] Síntesis de la semana {week} de «{job.workspace}»: "
        f"{len(concepts)} concepto(s), {themes} tema(s)"
    )
    return {"week": week, "concepts": len(concepts), "themes": themes}


def _groups(ws, week: str, user_ids: list[int]) -> list[tuple[str, list[Asked]]]:
    """Group a week's messages about the subject by concept, the most asked first.

    At most `DIGEST_MAX_CONCEPTS` concepts, each with its latest `DIGEST_MAX_MESSAGES`
    messages; the texts are read here, from their authors' files, and nowhere else.
    """
    reading = tutor_activity.read(ws, user_ids)
    by_concept: dict[str, list[activity.Message]] = defaultdict(list)
    for message in reading.messages:
        if message.on_subject and message.concept and activity.week_of(message.at) == week:
            by_concept[message.concept].append(message)
    chosen = sorted(by_concept.items(), key=lambda pair: (-len(pair[1]), pair[0]))
    chosen = chosen[: tutor_config.DIGEST_MAX_CONCEPTS]
    records: dict[tuple[int, str], dict | None] = {}
    groups = []
    for concept, messages in chosen:
        latest = sorted(messages, key=lambda m: m.at, reverse=True)[: tutor_config.DIGEST_MAX_MESSAGES]
        asked = []
        for message in latest:
            key = (message.user_id, message.conversation)
            if key not in records:
                records[key] = store.get(ws, message.user_id, message.conversation)
            turns = (records[key] or {}).get("turns") or []
            if message.turn < len(turns):
                text = str(turns[message.turn].get("text") or "")
                if text.strip():
                    asked.append(Asked(text, (message.user_id, message.conversation, message.turn)))
        if asked:
            groups.append((concept, asked))
    return groups
