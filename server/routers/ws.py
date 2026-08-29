"""The live stream.

One socket carries everything, ordered by `seq`. Reconnecting with `?since=N` replays
what was missed first and only then goes live, so a browser reload during a long run
does not create a hole in the timeline.

Authentication is decided **before** `accept()` — the cookie travels in the handshake, and
nothing is subscribed or replayed for a connection that has not earned it. What happens
after that decision differs by outcome: a welcome is an `accept()`, a refusal is an
`accept()` followed at once by close 4401, because that is the only way the code reaches
the browser (see `refuse` below). Until phase 2 this endpoint took any connection and
replayed the whole bus — logs, prompts and the token stream included — which with two users
meant one person's generated statements appearing in the other's browser. The filter is now
the server's, by workspace; the client still narrows by `job_id`, but only within what it
is entitled to see.

Which workspace a socket subscribes to arrives as `?workspace=`, because a browser cannot
set a header on a WebSocket handshake. It goes through the same membership check as the
`X-Workspace` header does over HTTP — asking for a workspace has never been the same as
being allowed into it.
"""

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import middleware, runtime
from ..auth import authenticate_socket

router = APIRouter()

HEARTBEAT_SECONDS = 20.0

# What a browser that has NEVER seen the stream is sent. A run emits one event per model
# token, so the buffer holds tens of thousands of `token` events and megabytes of text;
# replaying them into a fresh tab froze it for as long as the reducer took to chew — the
# «second person's screen goes white» bug. A cold connect gets the durable events only,
# bounded, and the `jobs` snapshot below is what guarantees the runs still carry their job
# even when `job.queued`/`job.started` have been evicted from the ring.
COLD_REPLAY_LIMIT = 4000
COLD_SKIPPED_KINDS = frozenset({"token"})

# How many jobs of the workspace travel in `stream.ready`. The client keeps 12 runs.
JOBS_SNAPSHOT_LIMIT = 20


def trim_cold_replay(events: list[dict]) -> list[dict]:
    kept = [e for e in events if e.get("kind") not in COLD_SKIPPED_KINDS]
    return kept[-COLD_REPLAY_LIMIT:]


# 4401 is the WebSocket convention for "unauthorised": the browser cannot read an HTTP
# status here, so the close code is the only way to tell the client to go and log in
# instead of reconnecting forever.
UNAUTHORISED = 4401


# And a close code only travels on an ESTABLISHED connection. Closing before `accept()`
# makes uvicorn answer the handshake with HTTP 403 and the browser synthesises a bare 1006:
# measured in a real browser, `{"code": 1006, "wasClean": false}` where the server believed
# it had said 4401. The client cannot tell that from a network hiccup, so it reconnected for
# ever against a cookie already rejected — the exact loop the code exists to prevent.
#
# Accepting first is what makes the code arrive. It costs an upgrade for somebody who is
# then told nothing: no subscription, no replay, not a single event.
async def refuse(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.close(code=UNAUTHORISED)


@router.websocket("/ws")
async def stream(websocket: WebSocket) -> None:
    # The origin is asked here and not by `OriginCheck`, which is a `BaseHTTPMiddleware`
    # and lets every non-`http` scope past untouched. Nothing was exploitable — a `Lax`
    # session cookie is not attached to a cross-site handshake — but the HTTP path
    # deliberately does not rely on `SameSite`, and the socket is the one place that was.
    # Same rule as over HTTP, from the same function: refuse on positive evidence of
    # cross-site, which leaves a CLI with no `Origin` connecting as it always did.
    #
    # 4401 and not a code of its own: our own client is same-origin, so the only thing that
    # can reach this branch is a page that is not ours, and a distinct code would tell it
    # apart from "no session" for free. Reusing it also means a deployment that misconfigures
    # `PUBLIC_BASE_URL` stops reconnecting instead of looping on an unknown code.
    if middleware.cross_site(websocket):
        await refuse(websocket)
        return

    access = await asyncio.to_thread(authenticate_socket, websocket)
    if access is None:
        await refuse(websocket)
        return

    await websocket.accept()
    slug = access.workspace.slug

    try:
        since = int(websocket.query_params.get("since", "0"))
    except ValueError:
        since = 0

    async with runtime.bus.subscribe() as queue:
        replayed, gap = runtime.bus.replay(since, workspace=slug)
        # `delivered` is computed BEFORE the cold trim: a trimmed event must not be
        # re-delivered from the live queue as if it were new.
        delivered = replayed[-1]["seq"] if replayed else since
        if since <= 0:
            replayed = trim_cold_replay(replayed)
        jobs = [
            job.to_dict()
            for job in runtime.runner.all(limit=JOBS_SNAPSHOT_LIMIT, workspace=slug)
        ]

        try:
            await websocket.send_json(
                {
                    "kind": "stream.ready",
                    "since": since,
                    "gap": gap,
                    "last_seq": runtime.bus.last_seq,
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
                        {"kind": "stream.heartbeat", "last_seq": runtime.bus.last_seq}
                    )
                    continue
                # The replay above and the live queue overlap by design; drop the
                # duplicates rather than risk a hole between them.
                if event.seq <= delivered:
                    continue
                delivered = event.seq
                if not runtime.bus.visible(event, slug):
                    continue
                await websocket.send_json(event.to_dict())
        except WebSocketDisconnect:
            return
        except RuntimeError:
            return
        finally:
            with contextlib.suppress(Exception):
                await websocket.close()
