"""Process-wide singletons: one bus and one queue, both now serving many workspaces.

The bus and the runner stay single because they model a single machine — one GPU, one
ordered stream — and that is unchanged. What used to be a third singleton, the
`ReviewState`, is gone: it is a path plus a small JSON, so there is one per workspace,
built where it is used. A shared one would have answered "approved" for whichever
instance happened to be read last.
"""

from variatio.core.workspace import Workspace

from .jobs import HANDLERS, EventBus, IdleUnloader, JobRunner, chain
from .model_pulls import PullTracker
from .review import ReviewState
from .tunnel import SshTunnel

bus = EventBus()
runner = JobRunner(bus, HANDLERS)
# A build's mandatory derivations enqueue themselves when it finishes. The queue knows
# nothing about the chain: it is installed here, where the process is assembled.
runner.after_success = chain.advance
# Neither bus nor queue: it only reads the queue's clock and releases the GPU after half
# an hour with nothing to do. Lives here because what it watches is the process, not a
# request.
idle_unloader = IdleUnloader(runner)
# The port forward to the GPU box, owned by this process so the panel can open and close
# it; and the model downloads, which are network and disk and never the GPU, so they run
# beside the queue rather than in it.
tunnel = SshTunnel()
pulls = PullTracker()


def review_state(ws: Workspace) -> ReviewState:
    return ReviewState(ws)


def building(ws: Workspace) -> set[str]:
    return runner.building_artifacts(ws.slug)


def pipeline_snapshot(ws: Workspace) -> list[dict]:
    return review_state(ws).snapshot(building(ws))
