"""In-memory keyword buffer for Bluesky Jetstream posts."""

import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

import websockets

logger = logging.getLogger(__name__)

# Disaster-related keywords for Latin America
DEFAULT_KEYWORDS = [
    "earthquake", "terremoto", "sismo", "temblor",
    "flood", "inundación", "inundacion",
    "hurricane", "huracán", "huracan", "ciclón", "ciclon",
    "wildfire", "incendio forestal",
    "volcano", "volcán", "volcan", "erupción", "erupcion",
    "tsunami",
    "landslide", "deslizamiento", "huaico",
    "drought", "sequía", "sequia",
    "deforestation", "deforestación", "deforestacion",
    "disaster", "desastre", "emergencia",
]

JETSTREAM_URL = "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"


@dataclass
class BlueskyPost:
    text: str
    author: str
    created_at: datetime
    keywords_matched: list[str]


@dataclass
class BlueskyBuffer:
    """Buffers recent Bluesky posts matching disaster keywords."""

    keywords: list[str] = field(default_factory=lambda: DEFAULT_KEYWORDS.copy())
    _buffer: deque[BlueskyPost] = field(default_factory=lambda: deque(maxlen=1000))
    _running: bool = False
    _total_processed: int = 0
    _total_matched: int = 0

    def search(self, query_keywords: list[str], max_results: int = 50) -> list[dict]:
        query_lower = [k.lower() for k in query_keywords]
        results = []
        for post in reversed(self._buffer):
            text_lower = post.text.lower()
            if any(kw in text_lower for kw in query_lower):
                results.append({
                    "text": post.text,
                    "author": post.author,
                    "created_at": post.created_at.isoformat(),
                    "keywords_matched": post.keywords_matched,
                })
                if len(results) >= max_results:
                    break
        return results

    def stats(self) -> dict:
        return {
            "buffer_size": len(self._buffer),
            "is_running": self._running,
            "keywords_count": len(self.keywords),
            "total_processed": self._total_processed,
            "total_matched": self._total_matched,
        }

    async def start(self) -> None:
        """Connect to Jetstream via WebSocket and buffer matching posts."""
        self._running = True
        logger.info("Starting Bluesky Jetstream listener...")

        while self._running:
            try:
                await self._connect()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Jetstream connection error: {e}. Reconnecting in 10s...")
                await asyncio.sleep(10)

    async def _connect(self) -> None:
        async for ws in websockets.connect(JETSTREAM_URL, ping_interval=30, ping_timeout=10):
            try:
                logger.info("Connected to Bluesky Jetstream (WebSocket)")
                async for msg in ws:
                    if not self._running:
                        return
                    try:
                        data = json.loads(msg)
                        self._process_message(data)
                    except json.JSONDecodeError:
                        continue
            except websockets.ConnectionClosed:
                if not self._running:
                    return
                logger.warning("Jetstream WebSocket closed. Reconnecting...")
                continue

    def _process_message(self, msg: dict) -> None:
        if msg.get("kind") != "commit":
            return
        commit = msg.get("commit", {})
        if commit.get("operation") != "create":
            return
        record = commit.get("record", {})
        text = record.get("text", "")
        if not text:
            return

        self._total_processed += 1

        text_lower = text.lower()
        matched = [kw for kw in self.keywords if kw.lower() in text_lower]
        if not matched:
            return

        self._total_matched += 1
        post = BlueskyPost(
            text=text,
            author=msg.get("did", "unknown"),
            created_at=datetime.now(timezone.utc),
            keywords_matched=matched,
        )
        self._buffer.append(post)

        if self._total_matched % 10 == 1:
            logger.info(
                f"Bluesky buffer: {self._total_matched} matched posts "
                f"(from {self._total_processed} processed, buffer: {len(self._buffer)})"
            )

    def stop(self) -> None:
        self._running = False


bluesky_buffer = BlueskyBuffer()
