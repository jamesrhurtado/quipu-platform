"""Public status page endpoint — no authentication required."""

import json

from fastapi import APIRouter, HTTPException

from db import db_connection

router = APIRouter(prefix="/api/status", tags=["status"])


@router.get("/{slug}")
async def get_public_status(slug: str):
    """Public status page for a municipality. No auth required."""
    async with db_connection() as conn:
        org = await conn.fetchrow(
            """
            SELECT id, name, municipality, department,
                   map_center_lat, map_center_lon
            FROM organizations
            WHERE slug = $1 AND is_active = true AND onboarding_completed = true
            """,
            slug,
        )

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org_id = org["id"]

    async with db_connection() as conn:
        # Latest risk assessment
        latest_risk = await conn.fetchrow(
            """
            SELECT risk_score, risk_level, explanation, created_at
            FROM risk_assessments
            WHERE org_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            org_id,
        )

        # Active (unacknowledged) alerts count
        active_alerts = await conn.fetchval(
            """
            SELECT COUNT(*) FROM alerts
            WHERE org_id = $1 AND acknowledged = false
              AND created_at > NOW() - INTERVAL '24 hours'
            """,
            org_id,
        )

        # Recent alerts (last 3)
        recent_alerts = await conn.fetch(
            """
            SELECT alert_level, risk_score, region, created_at
            FROM alerts
            WHERE org_id = $1
            ORDER BY created_at DESC
            LIMIT 3
            """,
            org_id,
        )

    return {
        "municipality": org["municipality"],
        "department": org["department"],
        "name": org["name"],
        "location": {
            "lat": org["map_center_lat"],
            "lon": org["map_center_lon"],
        },
        "risk": {
            "score": latest_risk["risk_score"] if latest_risk else None,
            "level": latest_risk["risk_level"] if latest_risk else "Unknown",
            "explanation": latest_risk["explanation"] if latest_risk else None,
            "updated_at": latest_risk["created_at"].isoformat() if latest_risk else None,
        },
        "active_alerts": active_alerts or 0,
        "recent_alerts": [
            {
                "alert_level": a["alert_level"],
                "risk_score": a["risk_score"],
                "region": a["region"],
                "created_at": a["created_at"].isoformat(),
            }
            for a in recent_alerts
        ],
    }
