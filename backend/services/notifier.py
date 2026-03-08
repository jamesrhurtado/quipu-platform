"""Notification delivery service — Teams webhooks and Bluesky posting."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# In-memory Bluesky token cache
_bluesky_token: str | None = None


def build_adaptive_card(
    alert_level: str,
    region: str,
    risk_score: float,
    explanation: str,
    drivers: list[dict[str, Any]] | None = None,
    dashboard_url: str = "http://localhost:3000",
) -> dict[str, Any]:
    """Build a Teams Adaptive Card payload for an alert."""
    color_map = {
        "elevated": "warning",
        "high": "attention",
        "critical": "attention",
    }
    accent = color_map.get(alert_level, "warning")

    emoji_map = {
        "elevated": "Warning",
        "high": "Warning",
        "critical": "Default",
    }

    facts = [
        {"title": "Region", "value": region},
        {"title": "Risk Score", "value": f"{risk_score}/5"},
        {"title": "Alert Level", "value": alert_level.upper()},
    ]
    if drivers:
        for d in drivers[:3]:
            facts.append({"title": d.get("label", ""), "value": d.get("reason", "")})

    card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": f"SENTINEL ALERT — {alert_level.upper()}",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": accent,
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Region: {region} | Risk: {risk_score}/5",
                            "spacing": "None",
                        },
                        {"type": "TextBlock", "text": explanation, "wrap": True},
                        {
                            "type": "FactSet",
                            "facts": facts,
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "View Dashboard",
                            "url": dashboard_url,
                        }
                    ],
                },
            }
        ],
    }
    return card


async def send_teams_webhook(webhook_url: str, card_payload: dict[str, Any]) -> dict[str, str]:
    """POST an Adaptive Card to a Teams incoming webhook. Returns delivery status."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json=card_payload, timeout=15)
            resp.raise_for_status()
        logger.info("Teams webhook delivered successfully")
        return {"status": "sent"}
    except Exception as e:
        logger.error(f"Teams webhook failed: {e}")
        return {"status": "failed", "error": str(e)}


async def post_to_bluesky(handle: str, app_password: str, text: str) -> dict[str, str]:
    """Post a message to Bluesky via the AT Protocol. Returns delivery status."""
    global _bluesky_token

    async def _authenticate(client: httpx.AsyncClient) -> str | None:
        global _bluesky_token
        try:
            resp = await client.post(
                "https://bsky.social/xrpc/com.atproto.server.createSession",
                json={"identifier": handle, "password": app_password},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            _bluesky_token = data["accessJwt"]
            return data.get("did")
        except Exception as e:
            logger.error(f"Bluesky auth failed: {e}")
            _bluesky_token = None
            return None

    async def _post(client: httpx.AsyncClient, did: str) -> dict[str, str]:
        from datetime import datetime, timezone

        record = {
            "repo": did,
            "collection": "app.bsky.feed.post",
            "record": {
                "$type": "app.bsky.feed.post",
                "text": text[:300],  # Bluesky 300-char limit
                "createdAt": datetime.now(timezone.utc).isoformat(),
            },
        }
        resp = await client.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            json=record,
            headers={"Authorization": f"Bearer {_bluesky_token}"},
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("Bluesky post delivered successfully")
        return {"status": "sent"}

    try:
        async with httpx.AsyncClient() as client:
            did = await _authenticate(client)
            if not did:
                return {"status": "failed", "error": "Authentication failed"}

            try:
                return await _post(client, did)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    # Token expired, re-authenticate
                    did = await _authenticate(client)
                    if not did:
                        return {"status": "failed", "error": "Re-authentication failed"}
                    return await _post(client, did)
                raise
    except Exception as e:
        logger.error(f"Bluesky post failed: {e}")
        return {"status": "failed", "error": str(e)}
