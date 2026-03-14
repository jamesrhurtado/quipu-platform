"""Alert escalation engine — threshold evaluation, cooldown, real + simulated notifications."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from config import settings
from db import get_pool
from services.sse_manager import sse_manager

logger = logging.getLogger(__name__)

# Risk score thresholds for alert levels
ALERT_THRESHOLDS = [
    ("critical", 4.5),
    ("high", 3.5),
    ("elevated", 2.5),
]

# Cooldown: don't re-alert same region+level within 30 minutes
COOLDOWN_MINUTES = 30

# Simulated notification targets by alert level
NOTIFICATION_TARGETS: dict[str, list[dict[str, str]]] = {
    "elevated": [
        {"type": "email", "target": "monitoring@sentinel-ops.lat", "label": "Quipu Ops Team"},
    ],
    "high": [
        {"type": "email", "target": "monitoring@sentinel-ops.lat", "label": "Quipu Ops Team"},
        {"type": "webhook", "target": "https://hooks.sentinel-ops.lat/alerts", "label": "Alert Dashboard"},
        {"type": "email", "target": "emergencias@defensa-civil.gob.pe", "label": "Civil Defense"},
    ],
    "critical": [
        {"type": "email", "target": "monitoring@sentinel-ops.lat", "label": "Quipu Ops Team"},
        {"type": "webhook", "target": "https://hooks.sentinel-ops.lat/alerts", "label": "Alert Dashboard"},
        {"type": "email", "target": "emergencias@defensa-civil.gob.pe", "label": "Civil Defense"},
        {"type": "sms", "target": "+51-1-XXX-XXXX", "label": "Emergency Coordinator"},
        {"type": "email", "target": "municipal_emergency@piura.gob.pe", "label": "Municipal Emergency Office"},
    ],
}


def _classify_alert_level(risk_score: float) -> str | None:
    """Determine alert level from risk score. Returns None if below threshold."""
    for level, threshold in ALERT_THRESHOLDS:
        if risk_score >= threshold:
            return level
    return None


async def _check_cooldown(region: str, alert_level: str, org_id: str | None = None) -> bool:
    """Check if we're still in cooldown for this region+level+org. Returns True if cooled down (ok to alert)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if org_id:
            row = await conn.fetchval(
                """
                SELECT COUNT(*) FROM alerts
                WHERE LOWER(region) = LOWER($1)
                  AND alert_level = $2
                  AND org_id = $3
                  AND created_at > NOW() - make_interval(mins => $4)
                """,
                region,
                alert_level,
                org_id,
                COOLDOWN_MINUTES,
            )
        else:
            row = await conn.fetchval(
                """
                SELECT COUNT(*) FROM alerts
                WHERE LOWER(region) = LOWER($1)
                  AND alert_level = $2
                  AND org_id IS NULL
                  AND created_at > NOW() - make_interval(mins => $3)
                """,
                region,
                alert_level,
                COOLDOWN_MINUTES,
            )
    return row == 0


async def _send_notifications(
    alert_level: str,
    region: str,
    risk_score: float,
    explanation: str = "",
    drivers: list | None = None,
    org_config: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Send real notifications where configured, simulate the rest.

    org_config: optional dict with keys teams_webhook_url, teams_enabled,
                bluesky_handle, bluesky_app_password (decrypted), bluesky_enabled,
                dashboard_url.
    If None, falls back to global settings.
    """
    actions = []

    # Resolve notification config — per-org or global
    teams_enabled = org_config["teams_enabled"] if org_config else settings.teams_enabled
    teams_webhook_url = org_config.get("teams_webhook_url") if org_config else settings.teams_webhook_url
    bsky_enabled = org_config["bluesky_enabled"] if org_config else (settings.bluesky_notifications_enabled and bool(settings.bluesky_handle))
    bsky_handle = org_config.get("bluesky_handle") if org_config else settings.bluesky_handle
    bsky_password = org_config.get("bluesky_app_password") if org_config else settings.bluesky_app_password
    dashboard_url = org_config.get("dashboard_url", settings.dashboard_url) if org_config else settings.dashboard_url

    # Teams: real delivery if enabled and webhook configured
    if teams_enabled and teams_webhook_url:
        try:
            from services.notifier import build_adaptive_card, send_teams_webhook

            card = build_adaptive_card(
                alert_level=alert_level,
                region=region,
                risk_score=risk_score,
                explanation=explanation,
                drivers=drivers,
                dashboard_url=dashboard_url,
            )
            result = await send_teams_webhook(teams_webhook_url, card)
            actions.append({
                "type": "teams",
                "target": teams_webhook_url[:50],
                "label": "Microsoft Teams",
                "status": result["status"],
                "message": f"[QUIPU ALERT] {alert_level.upper()} risk for {region} (score: {risk_score}/5)",
            })
        except Exception as e:
            logger.error(f"Teams notification error: {e}")
            actions.append({
                "type": "teams",
                "target": teams_webhook_url[:50],
                "label": "Microsoft Teams",
                "status": "failed",
                "message": str(e),
            })
    elif not teams_enabled:
        logger.debug("Teams notifications disabled")
    else:
        actions.append({
            "type": "teams",
            "target": "(not configured)",
            "label": "Microsoft Teams",
            "status": "simulated",
            "message": f"[QUIPU ALERT] {alert_level.upper()} risk for {region} (score: {risk_score}/5)",
        })

    # Bluesky: real delivery if enabled and credentials configured
    if bsky_enabled and bsky_handle and bsky_password:
        try:
            from services.notifier import post_to_bluesky

            level_es = {"elevated": "ELEVADO", "high": "ALTO", "critical": "CRITICO"}.get(alert_level, alert_level.upper())
            driver_lines = ""
            if drivers:
                for d in drivers[:2]:
                    driver_lines += f"\n• {d.get('label', '')}: {d.get('reason', '')}"
            text = (
                f"🚨 ALERTA QUIPU — {level_es}\n"
                f"📍 {region}\n"
                f"⚠️ Riesgo: {risk_score}/5\n"
                f"{driver_lines}\n"
                f"---\n"
                f"🚨 QUIPU ALERT — {alert_level.upper()}\n"
                f"Risk: {risk_score}/5 | {region}"
            )
            result = await post_to_bluesky(bsky_handle, bsky_password, text)
            actions.append({
                "type": "bluesky",
                "target": bsky_handle,
                "label": "Bluesky",
                "status": result["status"],
                "message": text[:200],
            })
        except Exception as e:
            logger.error(f"Bluesky notification error: {e}")
            actions.append({
                "type": "bluesky",
                "target": bsky_handle,
                "label": "Bluesky",
                "status": "failed",
                "message": str(e),
            })

    # Simulated fallback channels (email, SMS — not yet implemented)
    targets = NOTIFICATION_TARGETS.get(alert_level, [])
    for target in targets:
        actions.append({
            "type": target["type"],
            "target": target["target"],
            "label": target["label"],
            "status": "simulated",
            "message": f"[QUIPU ALERT] {alert_level.upper()} risk for {region} (score: {risk_score}/5)",
        })
        logger.info(
            f"[SIMULATED] {target['type']} notification to {target['target']} "
            f"for {alert_level.upper()} alert in {region}"
        )

    return actions


async def evaluate_and_alert(
    assessment: Any,
    org_id: str | None = None,
    org_config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Evaluate a risk assessment and trigger alerts if thresholds are exceeded.

    org_id: optional organization ID for scoped alerts.
    org_config: optional per-org notification config dict.
    Returns alert info dict if an alert was triggered, None otherwise.
    """
    alert_level = _classify_alert_level(assessment.risk_score)
    if not alert_level:
        return None

    # Check cooldown
    if not await _check_cooldown(assessment.region, alert_level, org_id=org_id):
        logger.info(
            f"Alert cooldown active for {assessment.region}/{alert_level}, skipping"
        )
        return None

    # Send real + simulated notifications
    actions = await _send_notifications(
        alert_level,
        assessment.region,
        assessment.risk_score,
        explanation=assessment.explanation or "",
        drivers=assessment.drivers,
        org_config=org_config,
    )

    # Persist alert
    drivers_json = json.dumps(assessment.drivers) if assessment.drivers else None
    actions_json = json.dumps(actions)

    pool = await get_pool()
    async with pool.acquire() as conn:
        alert_id = await conn.fetchval(
            """
            INSERT INTO alerts (region, alert_level, risk_score, risk_level, explanation, drivers, actions_taken, org_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            assessment.region,
            alert_level,
            assessment.risk_score,
            assessment.risk_level,
            assessment.explanation,
            drivers_json,
            actions_json,
            org_id,
        )

    alert_data = {
        "id": str(alert_id),
        "region": assessment.region,
        "alert_level": alert_level,
        "risk_score": assessment.risk_score,
        "risk_level": assessment.risk_level,
        "explanation": assessment.explanation,
        "drivers": assessment.drivers,
        "actions_taken": actions,
        "acknowledged": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Broadcast via SSE — scoped to org if provided
    await sse_manager.broadcast("alert", alert_data, org_id=org_id)

    logger.warning(
        f"ALERT TRIGGERED: {alert_level.upper()} for {assessment.region} "
        f"(risk_score={assessment.risk_score}, org_id={org_id})"
    )

    return alert_data
