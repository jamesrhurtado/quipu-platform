"""In-memory keyword buffer for Bluesky Jetstream posts."""

import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# Disaster-related keywords for Latin America
DEFAULT_KEYWORDS = [
    "earthquake", "terremoto", "sismo", "temblor",
    "flood", "inundación", "inundacion",
    "hurricane", "huracán", "huracan", "ciclón", "ciclon",
    "wildfire", "incendio forestal",
    "volcano", "volcán", "volcan", "erupción", "erupcion",
    "tsunami",
    "landslide", "deslizamiento",
    "drought", "sequía", "sequia",
    "deforestation", "deforestación", "deforestacion",
]

JETSTREAM_URL = "https://jetstream2.us-east.bsky.network/subscribe"


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
        }

    async def start(self) -> None:
        """Connect to Jetstream and buffer matching posts."""
        self._running = True
        logger.info("Starting Bluesky Jetstream listener...")

        while self._running:
            try:
                await self._connect()
            except Exception as e:
                logger.warning(f"Jetstream connection error: {e}. Reconnecting in 10s...")
                await asyncio.sleep(10)

    async def _connect(self) -> None:
        params = {
            "wantedCollections": "app.bsky.feed.post",
        }
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", JETSTREAM_URL, params=params) as resp:
                if resp.status_code != 200:
                    raise httpx.HTTPStatusError(
                        f"Jetstream returned {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                logger.info("Connected to Bluesky Jetstream")
                async for line in resp.aiter_lines():
                    if not self._running:
                        break
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                        self._process_message(msg)
                    except json.JSONDecodeError:
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

        text_lower = text.lower()
        matched = [kw for kw in self.keywords if kw.lower() in text_lower]
        if not matched:
            return

        post = BlueskyPost(
            text=text,
            author=msg.get("did", "unknown"),
            created_at=datetime.now(timezone.utc),
            keywords_matched=matched,
        )
        self._buffer.append(post)

    def stop(self) -> None:
        self._running = False


bluesky_buffer = BlueskyBuffer()
