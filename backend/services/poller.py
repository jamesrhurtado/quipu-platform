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
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_week.geojson"
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
        f"-118,-56,-34,33/3"
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


MONITORED_REGIONS = {
    "Peru": {"min_lat": -18, "max_lat": 0, "min_lon": -82, "max_lon": -68},
    "Cusco, Peru": {"min_lat": -15, "max_lat": -12, "min_lon": -73, "max_lon": -70},
    "Lima, Peru": {"min_lat": -13, "max_lat": -11, "min_lon": -78, "max_lon": -76},
    "Piura, Peru": {"min_lat": -6, "max_lat": -4, "min_lon": -81, "max_lon": -79},
    "Arequipa, Peru": {"min_lat": -18, "max_lat": -15, "min_lon": -73, "max_lon": -70},
    "Cajamarca, Peru": {"min_lat": -8, "max_lat": -4, "min_lon": -80, "max_lon": -77},
    "San Ramon, Chanchamayo, Peru": {"min_lat": -12, "max_lat": -10, "min_lon": -76, "max_lon": -74},
}


async def _assess_region(
    pool,
    region: str,
    bbox: dict,
    org_id: str | None = None,
    org_config: dict | None = None,
) -> None:
    """Run risk assessment for a single region/zone."""
    from agents.risk_engine import compute_risk
    from services.alert_engine import evaluate_and_alert

    async with pool.acquire() as conn:
        max_sev = await conn.fetchval(
            """
            SELECT COALESCE(MAX(severity), 1)
            FROM events
            WHERE created_at > NOW() - INTERVAL '24 hours'
              AND ST_Intersects(
                  coordinates,
                  ST_MakeEnvelope($1, $2, $3, $4, 4326)::geography
              )
            """,
            bbox["min_lon"], bbox["min_lat"], bbox["max_lon"], bbox["max_lat"],
        )

        fire_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM events
            WHERE event_type = 'wildfire'
              AND created_at > NOW() - INTERVAL '24 hours'
              AND ST_Intersects(
                  coordinates,
                  ST_MakeEnvelope($1, $2, $3, $4, 4326)::geography
              )
            """,
            bbox["min_lon"], bbox["min_lat"], bbox["max_lon"], bbox["max_lat"],
        )

    assessment = compute_risk(
        region=region,
        max_severity=float(max_sev),
        fire_count=int(fire_count),
        news_article_count=0,
        avg_confidence=0.7,
    )

    # Persist risk assessment
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO risk_assessments (region, risk_score, risk_level, components, explanation, org_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            assessment.region,
            assessment.risk_score,
            assessment.risk_level,
            json.dumps(assessment.components),
            assessment.explanation,
            org_id,
        )

    # Evaluate alert threshold
    if assessment.risk_score >= 3.0:
        await evaluate_and_alert(assessment, org_id=org_id, org_config=org_config)


async def _auto_risk_legacy() -> None:
    """Legacy risk assessment using hardcoded MONITORED_REGIONS."""
    pool = await get_pool()
    for region, bbox in MONITORED_REGIONS.items():
        try:
            await _assess_region(pool, region, bbox)
        except Exception as e:
            logger.error(f"Auto-risk failed for {region}: {e}")


async def _auto_risk_multi_tenant() -> None:
    """Multi-tenant risk assessment — iterate all active orgs and their monitored zones."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        orgs = await conn.fetch(
            """
            SELECT o.id, o.municipality, o.department,
                   o.teams_webhook_url, o.teams_enabled,
                   o.bluesky_handle, o.bluesky_app_password_encrypted, o.bluesky_enabled
            FROM organizations o
            WHERE o.is_active = true AND o.onboarding_completed = true
            """
        )

    for org in orgs:
        org_id = str(org["id"])

        # Build per-org notification config
        org_config = {
            "teams_webhook_url": org["teams_webhook_url"],
            "teams_enabled": org["teams_enabled"],
            "bluesky_handle": org["bluesky_handle"],
            "bluesky_app_password": None,
            "bluesky_enabled": org["bluesky_enabled"],
            "dashboard_url": settings.dashboard_url,
        }
        # Decrypt Bluesky password if present
        if org["bluesky_app_password_encrypted"]:
            try:
                from services.encryption import decrypt
                org_config["bluesky_app_password"] = decrypt(org["bluesky_app_password_encrypted"])
            except Exception as e:
                logger.error(f"Failed to decrypt Bluesky password for org {org_id}: {e}")

        # Get monitored zones for this org
        async with pool.acquire() as conn:
            zones = await conn.fetch(
                "SELECT name, bbox_min_lat, bbox_max_lat, bbox_min_lon, bbox_max_lon FROM monitored_zones WHERE org_id = $1",
                org["id"],
            )

        for zone in zones:
            region = f"{zone['name']}, {org['department'] or 'Peru'}"
            bbox = {
                "min_lat": zone["bbox_min_lat"],
                "max_lat": zone["bbox_max_lat"],
                "min_lon": zone["bbox_min_lon"],
                "max_lon": zone["bbox_max_lon"],
            }
            try:
                await _assess_region(pool, region, bbox, org_id=org_id, org_config=org_config)
            except Exception as e:
                logger.error(f"Auto-risk failed for {region} (org={org_id}): {e}")


async def auto_risk_step() -> None:
    """Automatic risk assessment. Dual-mode: legacy or multi-tenant."""
    if settings.multi_tenant_enabled:
        await _auto_risk_multi_tenant()
    else:
        await _auto_risk_legacy()


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

                # Auto-risk assessment for monitored regions
                try:
                    await auto_risk_step()
                    logger.info("Auto-risk step complete")
                except Exception as e:
                    logger.error(f"Auto-risk step error: {e}")
            except Exception as e:
                logger.error(f"Poll cycle error: {e}")

            await asyncio.sleep(settings.poll_interval_seconds)
