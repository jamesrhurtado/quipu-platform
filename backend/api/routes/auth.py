"""Authentication endpoints."""

from fastapi import APIRouter, Depends

from auth import AuthenticatedUser, get_current_user
from db import db_connection

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
async def get_me(user: AuthenticatedUser = Depends(get_current_user)):
    """Return current user info and org context."""
    org_data = None
    if user.org_id:
        async with db_connection() as conn:
            org = await conn.fetchrow(
                """
                SELECT id, name, slug, municipality, department,
                       map_center_lat, map_center_lon, map_zoom,
                       onboarding_completed
                FROM organizations WHERE id = $1
                """,
                user.org_id,
            )
            if org:
                org_data = {
                    "id": str(org["id"]),
                    "name": org["name"],
                    "slug": org["slug"],
                    "municipality": org["municipality"],
                    "department": org["department"],
                    "map_center_lat": org["map_center_lat"],
                    "map_center_lon": org["map_center_lon"],
                    "map_zoom": org["map_zoom"],
                    "onboarding_completed": org["onboarding_completed"],
                }

    return {
        "user": {
            "id": user.user_id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
        },
        "organization": org_data,
    }
