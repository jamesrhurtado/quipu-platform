"""Alert REST endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException

from auth import TenantContext, get_tenant
from config import settings
from db import get_pool

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    acknowledged: bool | None = None,
    limit: int = 50,
    tenant: TenantContext = Depends(get_tenant),
):
    """List alerts, optionally filtered by acknowledged status."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Scope to org when multi-tenant is active
        org_filter = ""
        params: list = []
        idx = 1

        if settings.multi_tenant_enabled and tenant.org_id:
            org_filter = f"org_id = ${idx}"
            params.append(tenant.org_id)
            idx += 1

        conditions = []
        if org_filter:
            conditions.append(org_filter)
        if acknowledged is not None:
            conditions.append(f"acknowledged = ${idx}")
            params.append(acknowledged)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = await conn.fetch(
            f"""
            SELECT id, region, alert_level, risk_score, risk_level,
                   explanation, drivers, actions_taken, acknowledged, created_at
            FROM alerts
            {where}
            ORDER BY created_at DESC
            LIMIT ${idx}
            """,
            *params,
            limit,
        )

    return {
        "alerts": [
            {
                "id": str(r["id"]),
                "region": r["region"],
                "alert_level": r["alert_level"],
                "risk_score": r["risk_score"],
                "risk_level": r["risk_level"],
                "explanation": r["explanation"],
                "drivers": json.loads(r["drivers"]) if r["drivers"] else [],
                "actions_taken": json.loads(r["actions_taken"]) if r["actions_taken"] else [],
                "acknowledged": r["acknowledged"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.patch("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Mark an alert as acknowledged."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE alerts SET acknowledged = true WHERE id = $1",
            alert_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Alert not found")

    return {"status": "acknowledged", "id": alert_id}
