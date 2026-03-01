"""SSE endpoint for real-time event streaming."""

import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from services.sse_manager import sse_manager

router = APIRouter()


async def _event_generator(request: Request):
    queue = sse_manager.subscribe()
    try:
        # Send initial connection confirmation
        yield {"event": "connected", "data": json.dumps({"status": "ok"})}

        while True:
            if await request.is_disconnected():
                break
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield msg
            except asyncio.TimeoutError:
                # Send keepalive
                yield {"event": "keepalive", "data": ""}
    finally:
        sse_manager.unsubscribe(queue)


@router.get("/api/stream")
async def event_stream(request: Request):
    """SSE endpoint for real-time event updates."""
    return EventSourceResponse(_event_generator(request))
