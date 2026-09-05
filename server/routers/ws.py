"""The live stream.

One socket carries everything, ordered by `seq`. Reconnecting with `?since=N` replays
what was missed first and only then goes live, so a browser reload during a long run does
not leave a hole in the timeline.

AUTHENTICATION IS DECIDED BEFORE `accept()`. The cookie travels in the handshake, and
nothing is subscribed or replayed for a connection that has not earned it — this endpoint
used to take any connection and replay the whole bus, logs, prompts and token stream
included, which with two users put one person's generated statements in the other's
browser. Every event carries the workspace the bus stamped on it and `bus.visible()` is
the filter; the client still narrows by `job_id`, but only within what it may see.

Which workspace a socket subscribes to arrives as `?workspace=`, because a browser cannot
set a header on a WebSocket handshake. It goes through the same membership check as the
`X-Workspace` header does over HTTP.
"""

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import middleware, singletons
from ..auth import authenticate_socket

router = APIRouter()

HEARTBEAT_SECONDS = 20.0

# What a browser that has NEVER seen the stream is sent. A run emits one event per model
# token, so the buffer holds tens of thousands of them and megabytes of text: replaying
# that into a fresh tab froze it for as long as the reducer took to chew. A cold connect
# gets the durable events only, bounded, and the `jobs` snapshot is what guarantees the
# runs still carry their job when `job.queued`/`job.started` have left the ring.
COLD_REPLAY_LIMIT = 4000
COLD_SKIPPED_KINDS = frozenset({"token"})

# How many jobs of the workspace travel in `stream.ready`. The client keeps 12 runs.
JOBS_SNAPSHOT_LIMIT = 20


def trim_cold_replay(events: list[dict]) -> list[dict]:
    """Cut a cold connect's replay down to the durable events, most recent last."""
    kept = [e for e in events if e.get("kind") not in COLD_SKIPPED_KINDS]
    return kept[-COLD_REPLAY_LIMIT:]


# The WebSocket convention for «unauthorised». A browser cannot read an HTTP status here,
# so the close code is the only way to tell the client to go and log in rather than
# reconnect for ever.
UNAUTHORISED = 4401


async def refuse(websocket: WebSocket) -> None:
    """Accept the upgrade only to close it with 4401, which is how the code arrives.

    A close code only travels on an ESTABLISHED connection: closing before `accept()`
    makes uvicorn answer the handshake with HTTP 403 and the browser synthesises a bare
    1006, which it cannot tell from a network hiccup — so it reconnects for ever against a
    cookie already rejected. Accepting first costs an upgrade for somebody who is then
    told nothing: no subscription, no replay, not a single event.
    """
    await websocket.accept()
    await websocket.close(code=UNAUTHORISED)


def _since(websocket: WebSocket) -> int:
    """Read `?since=`, treating anything unparseable as a cold connect."""
    try:
        return int(websocket.query_params.get("since", "0"))
    except ValueError:
        return 0


def _backlog(since: int, slug: str) -> tuple[list[dict], bool, int]:
    """Replay this workspace's missed events, and say how far delivery has got.

    Called inside the subscription so nothing emitted between the two is lost.
    `delivered` is computed BEFORE the cold trim: a trimmed event must not come back from
    the live queue as if it were new.
    """
    replayed, gap = singletons.bus.replay(since, workspace=slug)
    delivered = replayed[-1]["seq"] if replayed else since
    if since <= 0:
        replayed = trim_cold_replay(replayed)
    return replayed, gap, delivered


@router.websocket("/ws")
async def stream(websocket: WebSocket) -> None:
    """Serve one subscriber: refuse, or replay the backlog and then go live.

    The origin is checked here and not by `OriginCheck`, which is a `BaseHTTPMiddleware`
    and lets every non-`http` scope past untouched: the HTTP path deliberately does not
    rely on `SameSite`, and the socket was the one place that did. Same rule and same
    function — refuse on positive evidence of cross-site, which leaves a CLI with no
    `Origin` connecting as it always did. It closes with 4401 rather than a code of its
    own: our client is same-origin, so a distinct code would only tell a foreign page
    apart from «no session» for free, and a misconfigured `PUBLIC_BASE_URL` stops
    reconnecting instead of looping on a code nothing recognises.
    """
    if middleware.cross_site(websocket):
        await refuse(websocket)
        return

    access = await asyncio.to_thread(authenticate_socket, websocket)
    if access is None:
        await refuse(websocket)
        return

    await websocket.accept()
    slug = access.workspace.slug
    since = _since(websocket)

    async with singletons.bus.subscribe() as queue:
        replayed, gap, delivered = _backlog(since, slug)
        jobs = [
            job.to_dict()
            for job in singletons.runner.all(limit=JOBS_SNAPSHOT_LIMIT, workspace=slug)
        ]

        try:
            await websocket.send_json(
                {
                    "kind": "stream.ready",
                    "since": since,
                    "gap": gap,
                    "last_seq": singletons.bus.last_seq,
                    "workspace": slug,
                    "jobs": jobs,
                    "events": replayed,
                }
            )
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    await websocket.send_json(
                        {"kind": "stream.heartbeat", "last_seq": singletons.bus.last_seq}
                    )
                    continue
                # The replay and the live queue overlap by design; drop the duplicates
                # rather than risk a hole between them.
                if event.seq <= delivered:
                    continue
                delivered = event.seq
                if not singletons.bus.visible(event, slug):
                    continue
                await websocket.send_json(event.to_dict())
        except WebSocketDisconnect:
            return
        except RuntimeError:
            return
        finally:
            with contextlib.suppress(Exception):
                await websocket.close()
