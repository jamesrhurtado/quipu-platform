"""REST endpoint for querying events with spatial filters."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from auth import TenantContext, get_tenant
from config import settings
from db import db_connection

router = APIRouter()


@router.get("/api/events")
async def get_events(
    min_lat: float | None = Query(None, ge=-90, le=90),
    max_lat: float | None = Query(None, ge=-90, le=90),
    min_lon: float | None = Query(None, ge=-180, le=180),
    max_lon: float | None = Query(None, ge=-180, le=180),
    hours: int = Query(168, ge=1, le=720),
    event_type: str | None = Query(None),
    source: str | None = Query(None),
    min_severity: int = Query(1, ge=1, le=5),
    limit: int = Query(500, ge=1, le=2000),
    tenant: TenantContext = Depends(get_tenant),
):
    """Query events within a bounding box and time range.

    When multi-tenant is active, defaults to the org's bbox.
    """
    # Use org bbox as default when no explicit bbox provided.
    # Expand the org bbox by ~3x so the map shows regional events
    # (the org bbox is typically ~1 degree, expand to ~3 degrees each side).
    EXPAND_DEG = 2.0  # ~220km expansion on each side
    effective_min_lat = min_lat if min_lat is not None else max(-90, tenant.bbox_min_lat - EXPAND_DEG)
    effective_max_lat = max_lat if max_lat is not None else min(90, tenant.bbox_max_lat + EXPAND_DEG)
    effective_min_lon = min_lon if min_lon is not None else max(-180, tenant.bbox_min_lon - EXPAND_DEG)
    effective_max_lon = max_lon if max_lon is not None else min(180, tenant.bbox_max_lon + EXPAND_DEG)

    since = datetime.now(timezone.utc).timestamp() - (hours * 3600)
    since_dt = datetime.fromtimestamp(since, tz=timezone.utc)

    conditions = [
        "ST_Intersects(coordinates, ST_MakeEnvelope($1, $2, $3, $4, 4326)::geography)",
        "created_at >= $5",
        "severity >= $6",
    ]
    params: list = [effective_min_lon, effective_min_lat, effective_max_lon, effective_max_lat, since_dt, min_severity]
    idx = 7

    if event_type:
        conditions.append(f"event_type = ${idx}")
        params.append(event_type)
        idx += 1

    if source:
        conditions.append(f"source = ${idx}")
        params.append(source)
        idx += 1

    where = " AND ".join(conditions)

    query = f"""
        SELECT id, external_id, source, event_type, title, description,
               severity, magnitude,
               ST_Y(coordinates::geometry) as lat,
               ST_X(coordinates::geometry) as lon,
               started_at, updated_at, created_at, is_active
        FROM events
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT ${idx}
    """
    params.append(limit)

    async with db_connection() as conn:
        rows = await conn.fetch(query, *params)

    return {
        "events": [
            {
                "id": str(row["id"]),
                "external_id": row["external_id"],
                "source": row["source"],
                "event_type": row["event_type"],
                "title": row["title"],
                "description": row["description"],
                "severity": row["severity"],
                "magnitude": row["magnitude"],
                "lat": row["lat"],
                "lon": row["lon"],
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "is_active": row["is_active"],
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.get("/api/events/stats")
async def get_event_stats():
    """Get summary statistics about stored events."""
    async with db_connection() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM events")
        by_source = await conn.fetch(
            "SELECT source, COUNT(*) as count FROM events GROUP BY source ORDER BY count DESC"
        )
        by_type = await conn.fetch(
            "SELECT event_type, COUNT(*) as count FROM events GROUP BY event_type ORDER BY count DESC"
        )
        recent = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE created_at > NOW() - INTERVAL '24 hours'"
        )

    return {
        "total_events": total,
        "last_24h": recent,
        "by_source": {row["source"]: row["count"] for row in by_source},
        "by_type": {row["event_type"]: row["count"] for row in by_type},
    }
