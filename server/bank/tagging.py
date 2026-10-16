"""Tagging the exercises a teacher picks: the gates the tagger needs, and queueing it.

`tag_item` is a job of the teacher who asked, in the queue's second class, since somebody
watches the concepts arrive. Passing a generated exercise into the bank
(`consumers.generation`) asks the same of the same tagger.
"""

from fastapi import HTTPException

from variatio.core import inference

from .. import auth
from ..core import process
from ..jobs.catalogue import TAG_ITEM
from ..pipeline.gates import gate_error


def refuse_tagging(access: auth.Access) -> None:
    """Refuse a tagging the chain or the engine would make fail: the gates of `tag`.

    Public because passing a generated exercise into the bank (`consumers.generation`) asks the
    same of the same tagger.
    """
    error = gate_error(access.ws, "tag")
    if error:
        raise HTTPException(409, error)
    if not inference.is_available():
        raise HTTPException(
            503,
            f"No hay conexión con el motor de inferencia '{inference.engine_name()}'. "
            "Elige tú los conceptos, o vuelve a intentarlo cuando esté en marcha.",
        )


def queue_tagging(access: auth.Access, items: list[str]) -> dict:
    """Queue `tag_item` on these exercises, as a job of the teacher who asked."""
    job = process.runner.submit(
        TAG_ITEM,
        {"items": items},
        workspace=access.ws.slug,
        user_id=access.user.id,
        user_name=access.user.name,
    )
    return {**job.to_dict(), "queue_position": process.runner.queue_position(job.id)}
