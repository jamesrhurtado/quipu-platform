"""Risk assessment API endpoints."""

from fastapi import APIRouter, Query

from db import get_pool

router = APIRouter(prefix="/api", tags=["risk"])


@router.get("/risk-assessments")
async def get_risk_assessments(
    region: str | None = Query(None, description="Filter by region name (case-insensitive partial match)"),
    limit: int = Query(20, ge=1, le=100),
):
    """Get recent risk assessments, optionally filtered by region."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if region:
            rows = await conn.fetch(
                """
                SELECT id, region, risk_score, risk_level, components, explanation, created_at
                FROM risk_assessments
                WHERE LOWER(region) LIKE LOWER($1)
                ORDER BY created_at DESC
                LIMIT $2
                """,
                f"%{region}%",
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, region, risk_score, risk_level, components, explanation, created_at
                FROM risk_assessments
                ORDER BY created_at DESC
                LIMIT $1
                """,
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
