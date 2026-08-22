"""Lo que sigue solo a una construcción, y hasta dónde puede llegar.

Una fase que TIENE que ocurrir no debería ser un botón. Al terminar el grafo hay que
escribir las descripciones —sin ellas ningún concepto tiene vector y el etiquetado no
existe—, decidir qué conceptos sirven como etiqueta y calentar los índices. Eran tres
pulsaciones en dos pantallas distintas y ninguna de las tres era opcional, así que las
encadena la construcción que las deja pendientes.

Lo que NO se encadena es lo que depende de un artefacto que puede no existir todavía.
Cada eslabón declara su condición: si no se cumple se salta, se dice en el registro y la
cadena sigue con el siguiente. En un workspace recién creado —grafo primero, perfil
todavía no— se saltan los tres y la construcción termina en el grafo, igual que antes.

Un eslabón que falla o se cancela corta la cadena: `advance` solo se llama tras un
trabajo que terminó bien.
"""

from loguru import logger

from variant_generator import stages
from variant_generator.workspace import Workspace

from .. import review, settings
from .models import JOB_LABELS, Job

# Qué arrastra cada trabajo detrás de sí. Solo la construcción del grafo tiene cadena:
# es la única cuyo resultado deja tres derivaciones obligatorias sin hacer.
CHAINS: dict[str, tuple[str, ...]] = {
    "build_kg": ("describe_concepts", "review_taggability", "index"),
}


def _profile_exists(ws: Workspace) -> str | None:
    if stages.exemplars_profile_path(ws) is None:
        return "este workspace todavía no tiene perfil de ejemplares"
    return None


# La etiquetabilidad se juzga contra las modalidades del perfil y contra ítems reales, así
# que su puerta es la misma que la de `routers/jobs.NEEDS_APPROVED`: el perfil aprobado.
# Con el perfil construido pero sin aprobar se salta y se sigue; no es un error.
def _profile_approved(ws: Workspace) -> str | None:
    reason = _profile_exists(ws)
    if reason is not None:
        return reason
    if review.ReviewState(ws).state(review.EXEMPLARS_PROFILE)["status"] != "approved":
        return "el perfil de ejemplares aún no está aprobado"
    return None


def _indexable(ws: Workspace) -> str | None:
    reason = _profile_exists(ws)
    if reason is not None:
        return reason
    if not ws.exemplars_bank_path.is_file():
        return "todavía no hay banco de ejemplares que indexar"
    return None


REQUIRES = {
    "describe_concepts": _profile_exists,
    "review_taggability": _profile_approved,
    "index": _indexable,
}


def advance(runner, job: Job) -> None:
    remaining = list(job.params.get("chain") or CHAINS.get(job.kind) or ())
    if not remaining:
        return

    ws = settings.workspace_for(job.workspace)
    while remaining:
        kind = remaining.pop(0)
        blocked = REQUIRES.get(kind, lambda _ws: None)(ws)
        label = JOB_LABELS.get(kind, kind)
        if blocked is not None:
            logger.info(f"[cadena] «{label}» se salta: {blocked}")
            continue
        runner.submit(
            kind,
            {"chain": remaining},
            workspace=job.workspace,
            user_id=job.user_id,
            user_name=job.user_name,
        )
        logger.info(f"[cadena] «{label}» encolado tras «{job.label}»")
        return
