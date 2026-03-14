"""Organization settings CRUD endpoints."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import AuthenticatedUser, TenantContext, get_current_user, get_tenant
from config import settings
from db import db_connection, get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


# --- Organization Info ---

@router.get("/organization")
async def get_organization(tenant: TenantContext = Depends(get_tenant)):
    """Get organization details."""
    async with db_connection() as conn:
        org = await conn.fetchrow(
            """
            SELECT id, name, slug, municipality, department, country,
                   bbox_min_lat, bbox_max_lat, bbox_min_lon, bbox_max_lon,
                   map_center_lat, map_center_lon, map_zoom,
                   teams_webhook_url, teams_enabled,
                   bluesky_handle, bluesky_enabled,
                   is_active, onboarding_completed, created_at, updated_at
            FROM organizations WHERE id = $1
            """,
            tenant.org_id,
        )

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Get monitored zones
    async with db_connection() as conn:
        zones = await conn.fetch(
            "SELECT id, name, bbox_min_lat, bbox_max_lat, bbox_min_lon, bbox_max_lon, is_primary FROM monitored_zones WHERE org_id = $1 ORDER BY is_primary DESC, name",
            tenant.org_id,
        )

    return {
        "organization": {
            "id": str(org["id"]),
            "name": org["name"],
            "slug": org["slug"],
            "municipality": org["municipality"],
            "department": org["department"],
            "country": org["country"],
            "map_center_lat": org["map_center_lat"],
            "map_center_lon": org["map_center_lon"],
            "map_zoom": org["map_zoom"],
            "created_at": org["created_at"].isoformat(),
        },
        "notifications": {
            "teams_webhook_url": org["teams_webhook_url"],
            "teams_enabled": org["teams_enabled"],
            "bluesky_handle": org["bluesky_handle"],
            "bluesky_enabled": org["bluesky_enabled"],
        },
        "monitored_zones": [
            {
                "id": str(z["id"]),
                "name": z["name"],
                "is_primary": z["is_primary"],
                "bbox": {
                    "min_lat": z["bbox_min_lat"],
                    "max_lat": z["bbox_max_lat"],
                    "min_lon": z["bbox_min_lon"],
                    "max_lon": z["bbox_max_lon"],
                },
            }
            for z in zones
        ],
    }


# --- Notification Config ---

class UpdateNotificationsRequest(BaseModel):
    teams_webhook_url: str | None = None
    teams_enabled: bool = False
    bluesky_handle: str | None = None
    bluesky_app_password: str | None = None  # only set if changing
    bluesky_enabled: bool = False


@router.put("/notifications")
async def update_notifications(
    req: UpdateNotificationsRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant),
):
    """Update notification configuration."""
    if user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owner/admin can update notifications")

    encrypted_bsky_pw = None
    if req.bluesky_app_password:
        from services.encryption import encrypt
        encrypted_bsky_pw = encrypt(req.bluesky_app_password)

    async with db_connection() as conn:
        if encrypted_bsky_pw:
            await conn.execute(
                """
                UPDATE organizations SET
                    teams_webhook_url = $1, teams_enabled = $2,
                    bluesky_handle = $3, bluesky_app_password_encrypted = $4, bluesky_enabled = $5,
                    updated_at = NOW()
                WHERE id = $6
                """,
                req.teams_webhook_url, req.teams_enabled,
                req.bluesky_handle, encrypted_bsky_pw, req.bluesky_enabled,
                tenant.org_id,
            )
        else:
            # Don't overwrite existing encrypted password
            await conn.execute(
                """
                UPDATE organizations SET
                    teams_webhook_url = $1, teams_enabled = $2,
                    bluesky_handle = $3, bluesky_enabled = $4,
                    updated_at = NOW()
                WHERE id = $5
                """,
                req.teams_webhook_url, req.teams_enabled,
                req.bluesky_handle, req.bluesky_enabled,
                tenant.org_id,
            )

    return {"status": "ok"}


@router.post("/test-teams")
async def test_teams_webhook(
    user: AuthenticatedUser = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant),
):
    """Send a test Teams card."""
    if not tenant.teams_webhook_url:
        raise HTTPException(status_code=400, detail="Teams webhook not configured")

    from services.notifier import build_adaptive_card, send_teams_webhook

    card = build_adaptive_card(
        alert_level="elevated",
        region=tenant.municipality,
        risk_score=2.5,
        explanation="Test notification from Quipu settings. Your Teams integration is working!",
        dashboard_url=settings.dashboard_url,
    )
    return await send_teams_webhook(tenant.teams_webhook_url, card)


@router.post("/test-bluesky")
async def test_bluesky_auth(
    user: AuthenticatedUser = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant),
):
    """Verify Bluesky credentials."""
    if not tenant.bluesky_handle or not tenant.bluesky_app_password_encrypted:
        raise HTTPException(status_code=400, detail="Bluesky not configured")

    from services.encryption import decrypt
    import httpx

    password = decrypt(tenant.bluesky_app_password_encrypted)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://bsky.social/xrpc/com.atproto.server.createSession",
                json={"identifier": tenant.bluesky_handle, "password": password},
                timeout=15,
            )
            resp.raise_for_status()
        return {"status": "ok", "message": "Bluesky credentials verified"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bluesky auth failed: {e}")


# --- Emergency Contacts ---

@router.get("/contacts")
async def list_contacts(tenant: TenantContext = Depends(get_tenant)):
    """Get emergency contacts for the organization."""
    async with db_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, role, phone, email, notify_on_level, is_active, created_at
            FROM emergency_contacts
            WHERE org_id = $1 AND is_active = true
            ORDER BY name
            """,
            tenant.org_id,
        )

    return {
        "contacts": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "role": r["role"],
                "phone": r["phone"],
                "email": r["email"],
                "notify_on_level": r["notify_on_level"],
            }
            for r in rows
        ],
        "count": len(rows),
    }


class ContactCreateRequest(BaseModel):
    name: str
    role: str | None = None
    phone: str | None = None
    email: str | None = None
    notify_on_level: list[str] = []


@router.post("/contacts")
async def add_contact(
    req: ContactCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant),
):
    """Add an emergency contact."""
    if user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owner/admin can manage contacts")

    async with db_connection() as conn:
        contact_id = await conn.fetchval(
            """
            INSERT INTO emergency_contacts (org_id, name, role, phone, email, notify_on_level)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            tenant.org_id, req.name, req.role, req.phone, req.email, req.notify_on_level,
        )

    return {"id": str(contact_id), "status": "created"}


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant),
):
    """Delete an emergency contact."""
    if user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owner/admin can manage contacts")

    async with db_connection() as conn:
        result = await conn.execute(
            "DELETE FROM emergency_contacts WHERE id = $1 AND org_id = $2",
            contact_id, tenant.org_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Contact not found")

    return {"status": "deleted"}


# --- Danger Zone ---

@router.delete("/organization")
async def delete_organization(
    user: AuthenticatedUser = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant),
):
    """Delete the organization (owner only). Soft-deletes by deactivating."""
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can delete the organization")

    async with db_connection() as conn:
        await conn.execute(
            "UPDATE organizations SET is_active = false, updated_at = NOW() WHERE id = $1",
            tenant.org_id,
        )
        # Unlink all users
        await conn.execute(
            "UPDATE users SET org_id = NULL WHERE org_id = $1",
            tenant.org_id,
        )

    return {"status": "deleted"}
