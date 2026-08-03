"""The live stream.

One socket carries everything, ordered by `seq`. Reconnecting with `?since=N` replays
what was missed first and only then goes live, so a browser reload during a long run
does not create a hole in the timeline. The client filters by `job_id`; the server
does not need to know which view is looking.
"""

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import runtime

router = APIRouter()

HEARTBEAT_SECONDS = 20.0


@router.websocket("/ws")
async def stream(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        since = int(websocket.query_params.get("since", "0"))
    except ValueError:
        since = 0

    async with runtime.bus.subscribe() as queue:
        replayed, gap = runtime.bus.replay(since)
        await websocket.send_json(
            {
                "kind": "stream.ready",
                "since": since,
                "gap": gap,
                "last_seq": runtime.bus.last_seq,
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
                await websocket.send_json(event.to_dict())
        except WebSocketDisconnect:
            return
        except RuntimeError:
            return
        finally:
            with contextlib.suppress(Exception):
                await websocket.close()
