"""Process-wide singletons: one bus and one queue, both now serving many workspaces.

The bus and the runner stay single because they model a single machine — one GPU, one
ordered stream — and that is unchanged. What used to be a third singleton, the
`ReviewState`, is gone: it is a path plus a small JSON, so there is one per workspace,
built where it is used. A shared one would have answered "approved" for whichever
instance happened to be read last.
"""

from variant_generator.workspace import Workspace

from .jobs import HANDLERS, EventBus, IdleUnloader, JobRunner, chain
from .review import ReviewState

bus = EventBus()
runner = JobRunner(bus, HANDLERS)
# Las derivaciones obligatorias de una construcción se encolan solas al terminar. La cola
# no sabe nada de la cadena: se la instalamos aquí, que es donde se monta el proceso.
runner.after_success = chain.advance
# Ni bus ni cola: solo mira el reloj de la cola y suelta la GPU cuando lleva media hora
# sin nada que hacer. Vive aquí porque lo que vigila es el proceso, no una petición.
idle_unloader = IdleUnloader(runner)


def review_state(ws: Workspace) -> ReviewState:
    return ReviewState(ws)


def building(ws: Workspace) -> set[str]:
    return runner.building_artifacts(ws.slug)


def pipeline_snapshot(ws: Workspace) -> list[dict]:
    return review_state(ws).snapshot(building(ws))
