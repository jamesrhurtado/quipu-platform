"""Background poller that fetches disaster data from APIs and stores in PostGIS.

No LLM calls — this is a cheap, continuous data ingestion loop.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx

from config import settings
from db import get_pool
from services.normalizer import (
    normalize_eonet_event,
    normalize_firms_fire,
    normalize_gdacs_event,
    normalize_usgs_earthquake,
)
from services.sse_manager import sse_manager

logger = logging.getLogger(__name__)


async def _upsert_event(conn, event: dict) -> bool:
    """Insert or update an event. Returns True if new."""
    result = await conn.fetchval(
        """
        INSERT INTO events (external_id, source, event_type, title, description,
                          severity, magnitude, coordinates, started_at, raw_data)
        VALUES ($1, $2, $3, $4, $5, $6, $7,
                ST_SetSRID(ST_MakePoint($8, $9), 4326)::geography,
                $10, $11::jsonb)
        ON CONFLICT (external_id) DO UPDATE SET
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            severity = EXCLUDED.severity,
            magnitude = EXCLUDED.magnitude,
            updated_at = NOW(),
            raw_data = EXCLUDED.raw_data
        RETURNING (xmax = 0) AS is_new
        """,
        event["external_id"],
        event["source"],
        event["event_type"],
        event["title"],
        event["description"],
        event["severity"],
        event["magnitude"],
        event["lon"],
        event["lat"],
        event["started_at"],
        json.dumps(event.get("raw_data", {})),
    )
    return result


async def poll_usgs(client: httpx.AsyncClient) -> int:
    """Fetch recent earthquakes from USGS."""
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
    try:
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        logger.info(f"USGS: fetched {len(features)} earthquakes")

        pool = await get_pool()
        new_count = 0
        async with pool.acquire() as conn:
            for feature in features:
                normalized = normalize_usgs_earthquake(feature)
                if normalized:
                    is_new = await _upsert_event(conn, normalized)
                    if is_new:
                        new_count += 1
                        await sse_manager.broadcast("new_event", {
                            "external_id": normalized["external_id"],
                            "source": normalized["source"],
                            "event_type": normalized["event_type"],
                            "title": normalized["title"],
                            "severity": normalized["severity"],
                            "lat": normalized["lat"],
                            "lon": normalized["lon"],
                        })
        logger.info(f"USGS: {new_count} new events stored")
        return new_count
    except Exception as e:
        logger.error(f"USGS poll failed: {e}")
        return 0


async def poll_gdacs(client: httpx.AsyncClient) -> int:
    """Fetch alerts from GDACS RSS feed."""
    url = "https://www.gdacs.org/xml/rss.xml"
    try:
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()

        # Parse GDACS XML — simplified extraction
        import xml.etree.ElementTree as ET

        root = ET.fromstring(resp.text)
        namespaces = {
            "gdacs": "http://www.gdacs.org",
            "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
        }

        items = root.findall(".//item")
        logger.info(f"GDACS: fetched {len(items)} alerts")

        pool = await get_pool()
        new_count = 0
        async with pool.acquire() as conn:
            for item in items:
                entry = {}
                for child in item:
                    tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    prefix = child.tag.split("}")[0].replace("{", "") if "}" in child.tag else ""
                    key = f"gdacs:{tag}" if "gdacs" in prefix else f"geo:{tag}" if "geo" in prefix else tag
                    entry[key] = child.text

                normalized = normalize_gdacs_event(entry)
                if normalized:
                    is_new = await _upsert_event(conn, normalized)
                    if is_new:
                        new_count += 1
                        await sse_manager.broadcast("new_event", {
                            "external_id": normalized["external_id"],
                            "source": normalized["source"],
                            "event_type": normalized["event_type"],
                            "title": normalized["title"],
                            "severity": normalized["severity"],
                            "lat": normalized["lat"],
                            "lon": normalized["lon"],
                        })
        logger.info(f"GDACS: {new_count} new events stored")
        return new_count
    except Exception as e:
        logger.error(f"GDACS poll failed: {e}")
        return 0


async def poll_eonet(client: httpx.AsyncClient) -> int:
    """Fetch events from NASA EONET."""
    url = "https://eonet.gsfc.nasa.gov/api/v3/events"
    params = {"status": "open", "limit": 50}
    if settings.nasa_api_key and settings.nasa_api_key != "DEMO_KEY":
        params["api_key"] = settings.nasa_api_key
    try:
        resp = await client.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        events = data.get("events", [])
        logger.info(f"EONET: fetched {len(events)} events")

        pool = await get_pool()
        new_count = 0
        async with pool.acquire() as conn:
            for event in events:
                normalized = normalize_eonet_event(event)
                if normalized:
                    is_new = await _upsert_event(conn, normalized)
                    if is_new:
                        new_count += 1
                        await sse_manager.broadcast("new_event", {
                            "external_id": normalized["external_id"],
                            "source": normalized["source"],
                            "event_type": normalized["event_type"],
                            "title": normalized["title"],
                            "severity": normalized["severity"],
                            "lat": normalized["lat"],
                            "lon": normalized["lon"],
                        })
        logger.info(f"EONET: {new_count} new events stored")
        return new_count
    except Exception as e:
        logger.error(f"EONET poll failed: {e}")
        return 0


async def poll_firms(client: httpx.AsyncClient) -> int:
    """Fetch active fire data from NASA FIRMS for Latin America."""
    if not settings.nasa_firms_map_key:
        logger.debug("FIRMS: no MAP_KEY configured, skipping")
        return 0

    # Latin America bounding box (approx)
    url = (
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{settings.nasa_firms_map_key}/VIIRS_SNPP_NRT/"
        f"-118,-56,-34,33/1"
    )
    try:
        resp = await client.get(url, timeout=60)
        resp.raise_for_status()

        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            return 0

        headers = lines[0].split(",")
        fires = []
        for line in lines[1:]:
            values = line.split(",")
            if len(values) == len(headers):
                fires.append(dict(zip(headers, values)))

        logger.info(f"FIRMS: fetched {len(fires)} fire detections")

        pool = await get_pool()
        new_count = 0
        async with pool.acquire() as conn:
            for fire in fires[:500]:  # Limit to avoid overwhelming DB
                normalized = normalize_firms_fire(fire)
                if normalized:
                    is_new = await _upsert_event(conn, normalized)
                    if is_new:
                        new_count += 1

        if new_count > 0:
            await sse_manager.broadcast("new_events_batch", {
                "source": "firms",
                "count": new_count,
                "event_type": "wildfire",
            })
        logger.info(f"FIRMS: {new_count} new fire events stored")
        return new_count
    except Exception as e:
        logger.error(f"FIRMS poll failed: {e}")
        return 0


async def run_poll_cycle(client: httpx.AsyncClient) -> dict:
    """Run all pollers concurrently."""
    results = await asyncio.gather(
        poll_usgs(client),
        poll_gdacs(client),
        poll_eonet(client),
        poll_firms(client),
        return_exceptions=True,
    )

    sources = ["usgs", "gdacs", "eonet", "firms"]
    summary = {}
    for source, result in zip(sources, results):
        if isinstance(result, Exception):
            logger.error(f"{source} poll error: {result}")
            summary[source] = {"error": str(result)}
        else:
            summary[source] = {"new_events": result}

    return summary


async def start_polling() -> None:
    """Main polling loop."""
    logger.info(f"Starting background poller (interval: {settings.poll_interval_seconds}s)")
    async with httpx.AsyncClient() as client:
        while True:
            try:
                logger.info("Starting poll cycle...")
                summary = await run_poll_cycle(client)
                total_new = sum(
                    v.get("new_events", 0)
                    for v in summary.values()
                    if isinstance(v, dict) and "new_events" in v
                )
                logger.info(f"Poll cycle complete: {total_new} new events total")
                await sse_manager.broadcast("poll_complete", {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "summary": summary,
                })
            except Exception as e:
                logger.error(f"Poll cycle error: {e}")

            await asyncio.sleep(settings.poll_interval_seconds)
