"""Onboarding endpoints — organization setup wizard."""

import json
import logging
import math
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import AuthenticatedUser, get_current_user
from config import settings
from db import db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["onboarding"])

# Load municipalities dataset
_MUNICIPALITIES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "peru_municipalities.json"
_municipalities: list[dict[str, Any]] = []


def _load_municipalities() -> list[dict[str, Any]]:
    global _municipalities
    if not _municipalities:
        with open(_MUNICIPALITIES_PATH) as f:
            _municipalities = json.load(f)
    return _municipalities


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _slugify(name: str, department: str) -> str:
    """Create a URL-friendly slug."""
    raw = f"{name}-{department}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug


@router.get("/municipalities")
async def list_municipalities(q: str | None = None):
    """Return searchable list of Peruvian municipalities."""
    municipalities = _load_municipalities()
    if q:
        q_lower = q.lower()
        municipalities = [
            m for m in municipalities
            if q_lower in m["name"].lower() or q_lower in m["department"].lower()
        ]
    return {"municipalities": municipalities, "count": len(municipalities)}


@router.get("/municipalities/{name}/nearby")
async def get_nearby_municipalities(name: str, radius_km: float = 100):
    """Get municipalities within radius_km of the named municipality."""
    municipalities = _load_municipalities()
    target = next((m for m in municipalities if m["name"].lower() == name.lower()), None)
    if not target:
        raise HTTPException(status_code=404, detail="Municipality not found")

    nearby = []
    for m in municipalities:
        if m["name"].lower() == name.lower():
            continue
        dist = _haversine_km(target["lat"], target["lon"], m["lat"], m["lon"])
        if dist <= radius_km:
            nearby.append({**m, "distance_km": round(dist, 1)})

    nearby.sort(key=lambda x: x["distance_km"])
    return {"municipality": target, "nearby": nearby, "radius_km": radius_km}


# --- Onboarding endpoints ---

class CreateOrgRequest(BaseModel):
    municipality_name: str
    additional_zones: list[str] = []  # names of nearby municipalities to also monitor


class NotificationConfigRequest(BaseModel):
    teams_webhook_url: str | None = None
    teams_enabled: bool = False
    bluesky_handle: str | None = None
    bluesky_app_password: str | None = None
    bluesky_enabled: bool = False


class EmergencyContactRequest(BaseModel):
    name: str
    role: str | None = None
    phone: str | None = None
    email: str | None = None
    notify_on_level: list[str] = []


class ContactsRequest(BaseModel):
    contacts: list[EmergencyContactRequest]


@router.post("/onboarding/organization")
async def create_organization(
    req: CreateOrgRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Step 1: Create organization from municipality selection."""
    municipalities = _load_municipalities()
    primary = next(
        (m for m in municipalities if m["name"].lower() == req.municipality_name.lower()),
        None,
    )
    if not primary:
        raise HTTPException(status_code=400, detail=f"Municipality '{req.municipality_name}' not found")

    slug = _slugify(primary["name"], primary["department"])
    bbox = primary["bbox"]

    async with db_connection() as conn:
        # Check slug uniqueness, append suffix if needed
        existing = await conn.fetchval("SELECT COUNT(*) FROM organizations WHERE slug = $1", slug)
        if existing > 0:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

        # Create organization
        org_id = await conn.fetchval(
            """
            INSERT INTO organizations (name, slug, municipality, department,
                bbox_min_lat, bbox_max_lat, bbox_min_lon, bbox_max_lon,
                map_center_lat, map_center_lon, map_zoom)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id
            """,
            f"Quipu — {primary['name']}",
            slug,
            primary["name"],
            primary["department"],
            bbox["min_lat"],
            bbox["max_lat"],
            bbox["min_lon"],
            bbox["max_lon"],
            primary["lat"],
            primary["lon"],
            10,
        )

        # Create primary monitored zone
        await conn.execute(
            """
            INSERT INTO monitored_zones (org_id, name, bbox_min_lat, bbox_max_lat, bbox_min_lon, bbox_max_lon, is_primary)
            VALUES ($1, $2, $3, $4, $5, $6, true)
            """,
            org_id,
            primary["name"],
            bbox["min_lat"],
            bbox["max_lat"],
            bbox["min_lon"],
            bbox["max_lon"],
        )

        # Create additional monitored zones
        for zone_name in req.additional_zones:
            zone = next(
                (m for m in municipalities if m["name"].lower() == zone_name.lower()),
                None,
            )
            if zone:
                zb = zone["bbox"]
                await conn.execute(
                    """
                    INSERT INTO monitored_zones (org_id, name, bbox_min_lat, bbox_max_lat, bbox_min_lon, bbox_max_lon, is_primary)
                    VALUES ($1, $2, $3, $4, $5, $6, false)
                    """,
                    org_id,
                    zone["name"],
                    zb["min_lat"],
                    zb["max_lat"],
                    zb["min_lon"],
                    zb["max_lon"],
                )

        # Link user to org as owner
        await conn.execute(
            "UPDATE users SET org_id = $1, role = 'owner' WHERE id = $2",
            org_id,
            user.user_id,
        )

    return {
        "organization": {
            "id": str(org_id),
            "name": f"Quipu — {primary['name']}",
            "slug": slug,
            "municipality": primary["name"],
            "department": primary["department"],
        }
    }


@router.put("/onboarding/notifications")
async def update_notifications(
    req: NotificationConfigRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Step 2: Configure notification channels."""
    if not user.org_id:
        raise HTTPException(status_code=400, detail="Create organization first")

    encrypted_bsky_pw = None
    if req.bluesky_app_password:
        from services.encryption import encrypt
        encrypted_bsky_pw = encrypt(req.bluesky_app_password)

    async with db_connection() as conn:
        await conn.execute(
            """
            UPDATE organizations SET
                teams_webhook_url = $1,
                teams_enabled = $2,
                bluesky_handle = $3,
                bluesky_app_password_encrypted = $4,
                bluesky_enabled = $5,
                updated_at = NOW()
            WHERE id = $6
            """,
            req.teams_webhook_url,
            req.teams_enabled,
            req.bluesky_handle,
            encrypted_bsky_pw,
            req.bluesky_enabled,
            user.org_id,
        )

    return {"status": "ok"}


@router.put("/onboarding/contacts")
async def update_contacts(
    req: ContactsRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Step 3: Add emergency contacts."""
    if not user.org_id:
        raise HTTPException(status_code=400, detail="Create organization first")

    async with db_connection() as conn:
        # Clear existing contacts and re-insert
        await conn.execute("DELETE FROM emergency_contacts WHERE org_id = $1", user.org_id)
        for c in req.contacts:
            await conn.execute(
                """
                INSERT INTO emergency_contacts (org_id, name, role, phone, email, notify_on_level)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                user.org_id,
                c.name,
                c.role,
                c.phone,
                c.email,
                c.notify_on_level,
            )

    return {"status": "ok", "count": len(req.contacts)}


@router.post("/onboarding/complete")
async def complete_onboarding(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Mark onboarding as complete."""
    if not user.org_id:
        raise HTTPException(status_code=400, detail="Create organization first")

    async with db_connection() as conn:
        await conn.execute(
            "UPDATE organizations SET onboarding_completed = true, updated_at = NOW() WHERE id = $1",
            user.org_id,
        )

    return {"status": "ok"}


@router.post("/onboarding/test-teams")
async def test_teams(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Send a test Teams notification."""
    if not user.org_id:
        raise HTTPException(status_code=400, detail="Create organization first")

    async with db_connection() as conn:
        org = await conn.fetchrow(
            "SELECT teams_webhook_url, municipality FROM organizations WHERE id = $1",
            user.org_id,
        )

    if not org or not org["teams_webhook_url"]:
        raise HTTPException(status_code=400, detail="Teams webhook not configured")

    from services.notifier import build_adaptive_card, send_teams_webhook

    card = build_adaptive_card(
        alert_level="elevated",
        region=org["municipality"],
        risk_score=2.5,
        explanation="This is a test notification from Quipu. If you see this, your Teams integration is working!",
        dashboard_url=settings.dashboard_url,
    )
    result = await send_teams_webhook(org["teams_webhook_url"], card)
    return result


@router.post("/onboarding/test-bluesky")
async def test_bluesky(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Verify Bluesky credentials (authenticate only, don't post)."""
    if not user.org_id:
        raise HTTPException(status_code=400, detail="Create organization first")

    async with db_connection() as conn:
        org = await conn.fetchrow(
            "SELECT bluesky_handle, bluesky_app_password_encrypted FROM organizations WHERE id = $1",
            user.org_id,
        )

    if not org or not org["bluesky_handle"] or not org["bluesky_app_password_encrypted"]:
        raise HTTPException(status_code=400, detail="Bluesky not configured")

    from services.encryption import decrypt
    import httpx

    password = decrypt(org["bluesky_app_password_encrypted"])
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://bsky.social/xrpc/com.atproto.server.createSession",
                json={"identifier": org["bluesky_handle"], "password": password},
                timeout=15,
            )
            resp.raise_for_status()
        return {"status": "ok", "message": "Bluesky credentials verified"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bluesky auth failed: {e}")
