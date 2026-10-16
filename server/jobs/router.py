"""The job queue: submitting work, watching it, and replaying what it said.

Declares `auth.VIEW` for the whole router, submitting and cancelling included, and decides
by kind inside: a student of the subject (`viewer`) queues a commission or a comparison
(`STUDENT_KINDS`) and cancels their own; everything else — a build, a transcription, an
indexing — takes a teacher, and a refusal says `role_too_low`.

A kind's own function may admit it before it is queued (`catalogue.ADMISSIONS`): a commission's
bounds — one live batch per account and subject, and a student's size and day — are
`consumers.generation`'s, registered when it is installed.

The chain's gates are enforced here and not merely drawn in the UI, so a stale artifact
cannot be silently consumed. A job is only ever visible to the workspace it was submitted
for: without that the id is a twelve-hex guess away from another instance's event log. A
private job (`catalogue.PRIVATE_KINDS`) is visible to its author alone, and answers anybody
else the same 404 as a job that does not exist, as a generated exercise does.
"""


from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from variatio.core import inference

from .. import auth, singletons
from ..auth import features
from ..db.models import EDITOR, VIEWER
from ..pipeline.gates import gate_error, transcription_error
from . import lanes
from .catalogue import ADMISSIONS, FEATURE_OF, JOB_LABELS, STUDENT_KINDS, Job

router = APIRouter(prefix="/api", tags=["jobs"], dependencies=[auth.VIEW])


class JobBody(BaseModel):
    """What to run, with what parameters, and whether to skip the chain's gates.

    `force` is a teacher's: a student's commission always waits for the construction to be
    closed, because what it would read is a subject still being corrected.
    """

    kind: str
    params: dict = {}
    force: bool = False


def _mine(job_id: str, access: auth.Access):
    """Load a job this account may see here, or 404.

    One of another instance does not exist here, and neither does another account's private
    job: the same sentence for both, because a 403 would confirm that the id names one.
    """
    job = singletons.runner.get(job_id)
    if job is None or job.workspace != access.ws.slug or not job.seen_by(access.user.id):
        raise HTTPException(404, f"No existe el trabajo '{job_id}'")
    return job


@router.post("/jobs")
def submit(
    body: JobBody, access: auth.Access = auth.VIEW, db: DbSession = Depends(auth.db)
) -> dict:
    """Queue one job, answering its position behind whatever is already on its lanes."""
    if body.kind not in JOB_LABELS:
        raise HTTPException(422, f"Trabajo desconocido: '{body.kind}'")

    teacher = auth.at_least(access, EDITOR)
    if body.kind not in STUDENT_KINDS and not teacher:
        raise HTTPException(
            403,
            "Ese trabajo es de quien da clase en la asignatura.",
            headers={"X-Error-Code": auth.ROLE_TOO_LOW},
        )

    # A kind that belongs to an optional function is that function's: this route must not be
    # a way round the dependency its own router declares. Generating is everybody's, but a
    # subject's teachers may close it to its students.
    feature = FEATURE_OF.get(body.kind) or (features.GENERATE if body.kind == "generate" else None)
    refused = feature and features.refusal(db, access.user, feature, access.workspace, access.role)
    if refused:
        raise HTTPException(403, refused, headers={"X-Error-Code": features.OFF_CODE})

    # Without an engine no job can succeed: every kind calls a model. `force` skips the
    # chain's gates, which are a teacher's decision, and never this, which is impossible.
    if not inference.is_available():
        raise HTTPException(
            503,
            f"No hay conexión con el motor de inferencia "
            f"'{inference.engine_name()}'. Arráncalo y vuelve a intentarlo.",
        )

    if not (body.force and teacher):
        error = gate_error(access.ws, body.kind)
        if error:
            raise HTTPException(409, error)

    # Outside `force`: the gates are the person's decision, two jobs writing one page
    # cache is not.
    error = transcription_error(access.ws, body.kind)
    if error:
        raise HTTPException(409, error)

    student = access.role == VIEWER

    def queue() -> Job:
        """Queue the job as asked; a student's is redacted on the bus."""
        return singletons.runner.submit(
            body.kind,
            body.params,
            workspace=access.ws.slug,
            user_id=access.user.id,
            user_name=access.user.name,
            redacted=student,
        )

    admit = ADMISSIONS.get(body.kind)
    job = queue() if admit is None else admit(db, access, body.params, queue)
    return {
        "job": job.to_dict(),
        "since": singletons.bus.last_seq,
        "queue_position": singletons.runner.queue_position(job.id),
    }


@router.get("/jobs")
def listing(limit: int = Query(50, ge=1, le=200), access: auth.Access = auth.VIEW) -> dict:
    """Answer the most recent jobs of this workspace that this account may see."""
    jobs = singletons.runner.all(limit, workspace=access.ws.slug, for_user=access.user.id)
    return {"jobs": [j.to_dict() for j in jobs]}


# Declared above `/jobs/{job_id}`: FastAPI matches in declaration order, so the other way
# round "current" would be read as a job id and answer "no existe el trabajo 'current'".
@router.get("/jobs/current")
def current(access: auth.Access = auth.VIEW) -> dict:
    """Answer this workspace's oldest running job, its queue, and whether a lane is held.

    `job` is the oldest run of YOUR workspace and not of the installation: with one job
    per lane there can be two at once, and blanking yours because somebody else's started
    first on the other lane would report "nada en ejecución" while your build runs.
    Whether a lane is held at all stays global — the machine is shared. Another account's
    private job is neither `job` nor in `queued`: what it is doing is its author's.
    """
    me = access.user.id
    running = singletons.runner.running()
    ours = [j for j in running if j.workspace == access.ws.slug and j.seen_by(me)]
    holders = [singletons.runner.current_in(backend) for backend in lanes.BACKENDS]
    held = [job for job in holders if job is not None]
    return {
        "job": ours[0].to_dict() if ours else None,
        "queued": [
            {**j.to_dict(), "queue_position": singletons.runner.queue_position(j.id)}
            for j in singletons.runner.pending(access.ws.slug)
            if j.seen_by(me)
        ],
        "engine_busy": bool(held),
        "engine_busy_elsewhere": any(j.workspace != access.ws.slug for j in held),
        "last_seq": singletons.bus.last_seq,
    }


@router.get("/jobs/{job_id}")
def detail(job_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Answer one job of this workspace, with how many are ahead of it."""
    job = _mine(job_id, access)
    return {"job": job.to_dict(), "queue_position": singletons.runner.queue_position(job_id)}


@router.delete("/jobs/{job_id}")
def cancel(job_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Ask one job of this workspace to stop at its next checkpoint.

    A student stops their own jobs and no other; a teacher stops any job they can see — every
    build, and their own commissions. Another account's private job is a 404 to both.
    """
    job = _mine(job_id, access)
    if job.user_id != access.user.id and not auth.at_least(access, EDITOR):
        raise HTTPException(
            403,
            "Solo puedes detener tus propios trabajos.",
            headers={"X-Error-Code": auth.ROLE_TOO_LOW},
        )
    return {"cancelled": singletons.runner.cancel(job_id)}


@router.get("/events")
def events(since: int = 0, access: auth.Access = auth.VIEW) -> dict:
    """Replay this workspace's events since `since`, saying whether any were lost.

    The router-level dependency already guarantees membership; the filter is passed
    explicitly anyway so "you may only replay your own events" is visible where the
    replay happens rather than inferred two files away.
    """
    replayed, gap = singletons.bus.replay(
        since, workspace=access.ws.slug, user_id=access.user.id
    )
    return {"events": replayed, "gap": gap, "last_seq": singletons.bus.last_seq}
