"""Azure Entra ID JWT validation and FastAPI auth dependencies."""

import logging
import time
from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from config import settings
from db import db_connection

logger = logging.getLogger(__name__)

# JWKS cache
_jwks_cache: dict | None = None
_jwks_cache_time: float = 0
_JWKS_CACHE_TTL = 3600  # 1 hour


async def _get_jwks() -> dict:
    """Fetch and cache JWKS from Azure Entra ID."""
    global _jwks_cache, _jwks_cache_time

    if _jwks_cache and (time.time() - _jwks_cache_time) < _JWKS_CACHE_TTL:
        return _jwks_cache

    url = (
        f"https://login.microsoftonline.com/{settings.azure_tenant_id}"
        f"/discovery/v2.0/keys"
    )
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cache_time = time.time()
        return _jwks_cache


def _get_signing_key(jwks: dict, kid: str) -> dict:
    """Find the signing key matching the token's kid."""
    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            return key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to find signing key",
    )


async def _validate_token(token: str) -> dict:
    """Validate an Azure Entra ID JWT and return its claims."""
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token header",
        )

    jwks = await _get_jwks()
    signing_key = _get_signing_key(jwks, unverified_header["kid"])

    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.azure_client_id,
            issuer=f"https://login.microsoftonline.com/{settings.azure_tenant_id}/v2.0",
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {e}",
        )

    return claims


@dataclass
class AuthenticatedUser:
    user_id: str  # our internal UUID
    entra_oid: str
    email: str
    display_name: str | None
    org_id: str | None
    role: str | None


@dataclass
class TenantContext:
    org_id: str
    org_name: str
    municipality: str
    department: str | None
    bbox_min_lat: float
    bbox_max_lat: float
    bbox_min_lon: float
    bbox_max_lon: float
    map_center_lat: float
    map_center_lon: float
    map_zoom: int
    teams_webhook_url: str | None
    teams_enabled: bool
    bluesky_handle: str | None
    bluesky_app_password_encrypted: str | None
    bluesky_enabled: bool


def _extract_bearer_token(request: Request) -> str:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    return auth_header[7:]


async def get_current_user(request: Request) -> AuthenticatedUser:
    """FastAPI dependency: validate JWT, upsert user, return AuthenticatedUser.

    When multi_tenant_enabled is False, returns a stub user for backward compatibility.
    """
    if not settings.multi_tenant_enabled:
        return AuthenticatedUser(
            user_id="00000000-0000-0000-0000-000000000000",
            entra_oid="stub",
            email="local@localhost",
            display_name="Local User",
            org_id=None,
            role="owner",
        )

    token = _extract_bearer_token(request)
    claims = await _validate_token(token)

    oid = claims.get("oid") or claims.get("sub")
    email = claims.get("preferred_username") or claims.get("email", "")
    display_name = claims.get("name")

    if not oid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user identifier",
        )

    # Upsert user
    async with db_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (entra_oid, email, display_name, last_login_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (entra_oid) DO UPDATE
                SET email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    last_login_at = NOW()
            RETURNING id, entra_oid, email, display_name, org_id, role
            """,
            oid,
            email,
            display_name,
        )

    return AuthenticatedUser(
        user_id=str(row["id"]),
        entra_oid=row["entra_oid"],
        email=row["email"],
        display_name=row["display_name"],
        org_id=str(row["org_id"]) if row["org_id"] else None,
        role=row["role"],
    )


async def get_tenant(
    user: AuthenticatedUser = Depends(get_current_user),
) -> TenantContext:
    """FastAPI dependency: require authenticated user with a completed org.

    When multi_tenant_enabled is False, returns a stub tenant for backward compat.
    """
    if not settings.multi_tenant_enabled:
        return TenantContext(
            org_id="00000000-0000-0000-0000-000000000000",
            org_name="Quipu (Local)",
            municipality="Peru",
            department=None,
            bbox_min_lat=-56.0,
            bbox_max_lat=33.0,
            bbox_min_lon=-118.0,
            bbox_max_lon=-34.0,
            map_center_lat=-10.0,
            map_center_lon=-65.0,
            map_zoom=4,
            teams_webhook_url=settings.teams_webhook_url or None,
            teams_enabled=settings.teams_enabled,
            bluesky_handle=settings.bluesky_handle or None,
            bluesky_app_password_encrypted=None,
            bluesky_enabled=settings.bluesky_enabled,
        )

    if not user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Onboarding not completed — no organization linked",
        )

    async with db_connection() as conn:
        org = await conn.fetchrow(
            """
            SELECT id, name, municipality, department,
                   bbox_min_lat, bbox_max_lat, bbox_min_lon, bbox_max_lon,
                   map_center_lat, map_center_lon, map_zoom,
                   teams_webhook_url, teams_enabled,
                   bluesky_handle, bluesky_app_password_encrypted, bluesky_enabled
            FROM organizations
            WHERE id = $1 AND is_active = true AND onboarding_completed = true
            """,
            user.org_id,
        )

    if not org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization not found or onboarding not completed",
        )

    return TenantContext(
        org_id=str(org["id"]),
        org_name=org["name"],
        municipality=org["municipality"],
        department=org["department"],
        bbox_min_lat=org["bbox_min_lat"],
        bbox_max_lat=org["bbox_max_lat"],
        bbox_min_lon=org["bbox_min_lon"],
        bbox_max_lon=org["bbox_max_lon"],
        map_center_lat=org["map_center_lat"],
        map_center_lon=org["map_center_lon"],
        map_zoom=org["map_zoom"],
        teams_webhook_url=org["teams_webhook_url"],
        teams_enabled=org["teams_enabled"],
        bluesky_handle=org["bluesky_handle"],
        bluesky_app_password_encrypted=org["bluesky_app_password_encrypted"],
        bluesky_enabled=org["bluesky_enabled"],
    )
