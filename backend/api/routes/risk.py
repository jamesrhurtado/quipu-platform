"""Risk assessment API endpoints."""

from fastapi import APIRouter, Depends, Query

from auth import TenantContext, get_tenant
from config import settings
from db import get_pool

router = APIRouter(prefix="/api", tags=["risk"])


@router.get("/risk-assessments")
async def get_risk_assessments(
    region: str | None = Query(None, description="Filter by region name (case-insensitive partial match)"),
    limit: int = Query(20, ge=1, le=100),
    tenant: TenantContext = Depends(get_tenant),
):
    """Get recent risk assessments, optionally filtered by region."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        conditions = []
        params: list = []
        idx = 1

        if settings.multi_tenant_enabled and tenant.org_id:
            conditions.append(f"org_id = ${idx}")
            params.append(tenant.org_id)
            idx += 1

        if region:
            conditions.append(f"LOWER(region) LIKE LOWER(${idx})")
            params.append(f"%{region}%")
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = await conn.fetch(
            f"""
            SELECT id, region, risk_score, risk_level, components, explanation, created_at
            FROM risk_assessments
            {where}
            ORDER BY created_at DESC
            LIMIT ${idx}
            """,
            *params,
            limit,
        )

    return {
        "count": len(rows),
        "assessments": [
            {
                "id": str(r["id"]),
                "region": r["region"],
                "risk_score": r["risk_score"],
                "risk_level": r["risk_level"],
                "components": r["components"],
                "explanation": r["explanation"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    }
