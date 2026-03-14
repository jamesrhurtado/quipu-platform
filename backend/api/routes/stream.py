"""SSE endpoint for real-time event streaming."""

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse

from config import settings
from db import db_connection
from services.sse_manager import sse_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Simple token-to-org cache (short-lived, avoids DB hit per SSE reconnect)
_token_org_cache: dict[str, tuple[str | None, float]] = {}
_CACHE_TTL = 300  # 5 min


async def _resolve_org_from_token(token: str) -> str | None:
    """Validate a JWT token and return the org_id, with caching."""
    if token in _token_org_cache:
        org_id, ts = _token_org_cache[token]
        if time.time() - ts < _CACHE_TTL:
            return org_id

    try:
        from auth import _validate_token
        claims = await _validate_token(token)
        oid = claims.get("oid") or claims.get("sub")
        if not oid:
            return None

        async with db_connection() as conn:
            row = await conn.fetchrow(
                "SELECT org_id FROM users WHERE entra_oid = $1", oid
            )
            org_id = str(row["org_id"]) if row and row["org_id"] else None
            _token_org_cache[token] = (org_id, time.time())
            return org_id
    except Exception:
        return None


async def _event_generator(request: Request, org_id: str | None = None):
    queue = sse_manager.subscribe(org_id=org_id)
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
async def event_stream(
    request: Request,
    token: str | None = Query(None),
):
    """SSE endpoint for real-time event updates.

    Auth via query param ?token=<jwt> since EventSource doesn't support headers.
    """
    org_id = None
    if settings.multi_tenant_enabled and token:
        org_id = await _resolve_org_from_token(token)

    return EventSourceResponse(_event_generator(request, org_id=org_id))
