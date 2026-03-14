import asyncio
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class _Subscriber:
    queue: asyncio.Queue
    org_id: str | None  # None = global subscriber (legacy / no multi-tenant)


@dataclass
class SSEManager:
    """Manages Server-Sent Event connections and broadcasts with org scoping."""

    _subscribers: list[_Subscriber] = field(default_factory=list)

    def subscribe(self, org_id: str | None = None) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(_Subscriber(queue=queue, org_id=org_id))
        logger.info(f"SSE client connected (org={org_id}). Total: {len(self._subscribers)}")
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers = [s for s in self._subscribers if s.queue is not queue]
        logger.info(f"SSE client disconnected. Total: {len(self._subscribers)}")

    async def broadcast(self, event_type: str, data: dict, org_id: str | None = None) -> None:
        """Broadcast an event.

        If org_id is None, sends to all subscribers (global events like new_event, poll_complete).
        If org_id is set, sends only to subscribers of that org (scoped events like alerts).
        """
        if not self._subscribers:
            return
        message = json.dumps(data, default=str)
        dead = []
        for sub in self._subscribers:
            # Global broadcast (org_id=None) goes to everyone
            # Scoped broadcast goes only to matching org or global subscribers
            if org_id is not None and sub.org_id is not None and sub.org_id != org_id:
                continue
            try:
                sub.queue.put_nowait({"event": event_type, "data": message})
            except asyncio.QueueFull:
                dead.append(sub)
        for d in dead:
            self._subscribers.remove(d)


sse_manager = SSEManager()
