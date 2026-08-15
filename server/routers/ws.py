"""The live stream.

One socket carries everything, ordered by `seq`. Reconnecting with `?since=N` replays
what was missed first and only then goes live, so a browser reload during a long run
does not create a hole in the timeline.

Authentication happens **before** `accept()`: the cookie travels in the handshake, and a
socket that has been accepted has already been told it is welcome. Until phase 2 this
endpoint took any connection and replayed the whole bus — logs, prompts and the token
stream included — which with two users meant one person's generated statements appearing
in the other's browser. The filter is now the server's, by workspace; the client still
narrows by `job_id`, but only within what it is entitled to see.
"""

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import runtime
from ..auth import authenticate_socket

router = APIRouter()

HEARTBEAT_SECONDS = 20.0

# 4401 is the WebSocket convention for "unauthorised": the browser cannot read an HTTP
# status here, so the close code is the only way to tell the client to go and log in
# instead of reconnecting forever.
UNAUTHORISED = 4401


@router.websocket("/ws")
async def stream(websocket: WebSocket) -> None:
    access = await asyncio.to_thread(authenticate_socket, websocket)
    if access is None:
        await websocket.close(code=UNAUTHORISED)
        return

    await websocket.accept()
    slug = access.workspace.slug

    try:
        since = int(websocket.query_params.get("since", "0"))
    except ValueError:
        since = 0

    async with runtime.bus.subscribe() as queue:
        replayed, gap = runtime.bus.replay(since, workspace=slug)
        await websocket.send_json(
            {
                "kind": "stream.ready",
                "since": since,
                "gap": gap,
                "last_seq": runtime.bus.last_seq,
                "workspace": slug,
                "events": replayed,
            }
        )
        delivered = replayed[-1]["seq"] if replayed else since

        try:
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
