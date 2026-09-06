"""Process-wide singletons: one bus and one queue, both serving many workspaces.

They stay single because they model this installation's whole capacity — one ordered stream
of events, and one arbiter of what may run beside what. That arbiter is not a single file of
work: `jobs/lanes.py` serialises per backend, so a local job and a remote one hold different
lanes and run at once. The `Approvals` reader is deliberately NOT a singleton — it is one
per workspace, built where it is used.
"""

from variatio.core.workspace import Workspace

from .jobs import HANDLERS, EventBus, IdleUnloader, JobRunner, chain
from .model_pulls import PullTracker
from .approvals import Approvals
from .tunnel import SshTunnel

bus = EventBus()
runner = JobRunner(bus, HANDLERS)
# The queue knows nothing about the chain, so a build's mandatory derivations are wired to
# enqueue themselves here, where the process is assembled.
runner.after_success = chain.advance
# Reads every lane of the queue's clock and releases the GPU after half an hour idle.
idle_unloader = IdleUnloader(runner)
# The port forward to the GPU box, and the model downloads — network and disk, never the
# GPU, so they run beside the queue rather than in it.
tunnel = SshTunnel()
pulls = PullTracker()


def approvals(ws: Workspace) -> Approvals:
    """Return a fresh `Approvals` reader for one workspace."""
    return Approvals(ws)


def building(ws: Workspace) -> set[str]:
    """The artifacts a job is building right now in one workspace."""
    return runner.building_artifacts(ws.slug)


def pipeline_snapshot(ws: Workspace) -> list[dict]:
    """The whole chain's state for one workspace, with what is building marked as such."""
    return approvals(ws).snapshot(building(ws))
