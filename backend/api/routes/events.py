"""REST endpoint for querying events with spatial filters."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from db import db_connection

router = APIRouter()


@router.get("/api/events")
async def get_events(
    min_lat: float = Query(-90, ge=-90, le=90),
    max_lat: float = Query(90, ge=-90, le=90),
    min_lon: float = Query(-180, ge=-180, le=180),
    max_lon: float = Query(180, ge=-180, le=180),
    hours: int = Query(48, ge=1, le=720),
    event_type: str | None = Query(None),
    source: str | None = Query(None),
    min_severity: int = Query(1, ge=1, le=5),
    limit: int = Query(500, ge=1, le=2000),
):
    """Query events within a bounding box and time range."""
    since = datetime.now(timezone.utc).timestamp() - (hours * 3600)
    since_dt = datetime.fromtimestamp(since, tz=timezone.utc)

    conditions = [
        "ST_Intersects(coordinates, ST_MakeEnvelope($1, $2, $3, $4, 4326)::geography)",
        "created_at >= $5",
        "severity >= $6",
    ]
    params: list = [min_lon, min_lat, max_lon, max_lat, since_dt, min_severity]
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
