import asyncio
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SSEManager:
    """Manages Server-Sent Event connections and broadcasts."""

    _subscribers: set[asyncio.Queue] = field(default_factory=set)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        logger.info(f"SSE client connected. Total: {len(self._subscribers)}")
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)
        logger.info(f"SSE client disconnected. Total: {len(self._subscribers)}")

    async def broadcast(self, event_type: str, data: dict) -> None:
        if not self._subscribers:
            return
        message = json.dumps(data, default=str)
        dead_queues = []
        for queue in self._subscribers:
            try:
                queue.put_nowait({"event": event_type, "data": message})
            except asyncio.QueueFull:
                dead_queues.append(queue)
        for q in dead_queues:
            self._subscribers.discard(q)


sse_manager = SSEManager()
