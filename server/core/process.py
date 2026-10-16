"""The process's live pieces: one bus and one queue serving many workspaces, the idle unloader,
the SSH tunnel and the model downloads.

The bus and the queue stay single because they model this installation's whole capacity — one
ordered stream of events, and one arbiter of what may run beside what. That arbiter is not a
single file of work: `jobs/lanes.py` serialises per backend, so a local job and a remote one
hold different lanes and run at once. The queue knows nothing about the chain, which
`server/app.py` wires to it (`pipeline.chain.wire`). The `Approvals` reader is deliberately
NOT one of these: it is one per workspace, built where it is used.
"""

from ..jobs import HANDLERS, EventBus, IdleUnloader, JobRunner
from .model_pulls import PullTracker
from .tunnel import SshTunnel

bus = EventBus()
runner = JobRunner(bus, HANDLERS)
# Reads every lane of the queue's clock and releases the GPU after half an hour idle.
idle_unloader = IdleUnloader(runner)
# The port forward to the GPU box, and the model downloads — network and disk, never the
# GPU, so they run beside the queue rather than in it.
tunnel = SshTunnel()
pulls = PullTracker()
