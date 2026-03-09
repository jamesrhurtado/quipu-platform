"""Notification agent tools — Teams alerts, Bluesky posts, and notification history."""

import json
import logging
from datetime import datetime, timezone
from typing import Annotated

from agent_framework import tool
from agents.scoring import wrap_tool_result
from config import settings
from db import get_pool

logger = logging.getLogger(__name__)


async def _log_notification(
    channel: str,
    recipient: str,
    alert_level: str,
    region: str,
    status: str,
    payload: dict | None = None,
) -> str:
    """Persist a notification record to the database. Returns the notification ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        nid = await conn.fetchval(
            """
            INSERT INTO notifications (channel, recipient, alert_level, region, status, payload)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            channel,
            recipient,
            alert_level,
            region,
            status,
            json.dumps(payload) if payload else None,
        )
    return str(nid)


@tool
async def send_teams_alert(
    region: Annotated[str, "Region the alert is about (e.g. 'Cusco, Peru')"],
    alert_level: Annotated[str, "Alert level: elevated, high, or critical"],
    risk_score: Annotated[float, "Risk score (1.0-5.0)"],
    summary: Annotated[str, "Summary explanation of the risk situation"],
    key_facts: Annotated[str, "Comma-separated key facts to include in the card"] = "",
) -> str:
    """Send an alert to Microsoft Teams via Adaptive Card webhook."""
    from services.notifier import build_adaptive_card, send_teams_webhook

    if not settings.teams_enabled:
        return wrap_tool_result(
            {
                "status": "disabled",
                "channel": "teams",
                "message": "Teams notifications are disabled (TEAMS_ENABLED=false).",
                "region": region,
                "alert_level": alert_level,
            },
            source="NotificationAgent",
            timestamps=[datetime.now(timezone.utc).isoformat()],
        )

    if not settings.teams_webhook_url:
        await _log_notification(
            channel="teams",
            recipient="(not configured)",
            alert_level=alert_level,
            region=region,
            status="simulated",
            payload={"summary": summary},
        )
        return wrap_tool_result(
            {
                "status": "simulated",
                "channel": "teams",
                "message": "Teams webhook URL not configured. Alert simulated.",
                "region": region,
                "alert_level": alert_level,
            },
            source="NotificationAgent",
            timestamps=[datetime.now(timezone.utc).isoformat()],
        )

    drivers = []
    if key_facts:
        for fact in key_facts.split(","):
            fact = fact.strip()
            if fact:
                drivers.append({"label": fact, "reason": fact})

    card = build_adaptive_card(
        alert_level=alert_level,
        region=region,
        risk_score=risk_score,
        explanation=summary,
        drivers=drivers,
        dashboard_url=settings.dashboard_url,
    )

    result = await send_teams_webhook(settings.teams_webhook_url, card)
    status = result["status"]

    await _log_notification(
        channel="teams",
        recipient=settings.teams_webhook_url[:50],
        alert_level=alert_level,
        region=region,
        status=status,
        payload={"summary": summary, "risk_score": risk_score},
    )

    return wrap_tool_result(
        {
            "status": status,
            "channel": "teams",
            "region": region,
            "alert_level": alert_level,
            "risk_score": risk_score,
            "message": f"Teams alert {'delivered' if status == 'sent' else 'failed'} for {region}",
        },
        source="NotificationAgent",
        timestamps=[datetime.now(timezone.utc).isoformat()],
    )


@tool
async def post_bluesky_alert(
    region: Annotated[str, "Region the alert is about"],
    alert_level: Annotated[str, "Alert level: elevated, high, or critical"],
    risk_score: Annotated[float, "Risk score (1.0-5.0)"],
    summary: Annotated[str, "Brief summary of the situation"],
) -> str:
    """Post a bilingual (Spanish/English) alert to Bluesky for public advisory."""
    from services.notifier import post_to_bluesky

    if not settings.bluesky_notifications_enabled:
        return wrap_tool_result(
            {
                "status": "disabled",
                "channel": "bluesky",
                "message": "Bluesky notifications are disabled (BLUESKY_NOTIFICATIONS_ENABLED=false).",
                "region": region,
                "alert_level": alert_level,
            },
            source="NotificationAgent",
            timestamps=[datetime.now(timezone.utc).isoformat()],
        )

    if not settings.bluesky_handle or not settings.bluesky_app_password:
        await _log_notification(
            channel="bluesky",
            recipient="(not configured)",
            alert_level=alert_level,
            region=region,
            status="simulated",
            payload={"summary": summary},
        )
        return wrap_tool_result(
            {
                "status": "simulated",
                "channel": "bluesky",
                "message": "Bluesky credentials not configured. Alert simulated.",
                "region": region,
                "alert_level": alert_level,
            },
            source="NotificationAgent",
            timestamps=[datetime.now(timezone.utc).isoformat()],
        )

    level_es = {"elevated": "ELEVADO", "high": "ALTO", "critical": "CRITICO"}.get(alert_level, alert_level.upper())

    # Bilingual text: Spanish first, English second
    text = (
        f"ALERTA QUIPU — {level_es}\n"
        f"{region} — Riesgo: {risk_score}/5\n"
        f"{summary[:120]}\n"
        f"---\n"
        f"QUIPU ALERT — {alert_level.upper()}\n"
        f"Risk: {risk_score}/5 | {region}"
    )

    result = await post_to_bluesky(settings.bluesky_handle, settings.bluesky_app_password, text)
    status = result["status"]

    await _log_notification(
        channel="bluesky",
        recipient=settings.bluesky_handle,
        alert_level=alert_level,
        region=region,
        status=status,
        payload={"summary": summary, "risk_score": risk_score, "text": text[:300]},
    )

    return wrap_tool_result(
        {
            "status": status,
            "channel": "bluesky",
            "region": region,
            "alert_level": alert_level,
            "message": f"Bluesky post {'delivered' if status == 'sent' else 'failed'} for {region}",
        },
        source="NotificationAgent",
        timestamps=[datetime.now(timezone.utc).isoformat()],
    )


@tool
async def get_notification_history(
    region: Annotated[str, "Region to filter by, or 'all' for all regions"] = "all",
    hours_back: Annotated[int, "Number of hours to look back"] = 24,
    limit: Annotated[int, "Maximum number of records to return"] = 20,
) -> str:
    """Query the notification audit trail for recent alerts sent via Teams, Bluesky, etc."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if region == "all":
            rows = await conn.fetch(
                """
                SELECT id, channel, recipient, alert_level, region, status, payload, created_at
                FROM notifications
                WHERE created_at > NOW() - make_interval(hours => $1)
                ORDER BY created_at DESC
                LIMIT $2
                """,
                hours_back,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, channel, recipient, alert_level, region, status, payload, created_at
                FROM notifications
                WHERE LOWER(region) LIKE LOWER($1)
                  AND created_at > NOW() - make_interval(hours => $2)
                ORDER BY created_at DESC
                LIMIT $3
                """,
                f"%{region}%",
                hours_back,
                limit,
            )

    results = []
    timestamps = []
    for r in rows:
        results.append({
            "id": str(r["id"]),
            "channel": r["channel"],
            "recipient": r["recipient"],
            "alert_level": r["alert_level"],
            "region": r["region"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat(),
        })
        timestamps.append(r["created_at"].isoformat())

    return wrap_tool_result(
        {
            "count": len(results),
            "notifications": results,
            "query": {"region": region, "hours_back": hours_back},
        },
        source="NotificationAgent",
        timestamps=timestamps,
    )
