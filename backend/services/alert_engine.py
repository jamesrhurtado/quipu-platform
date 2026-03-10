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
    ("high", 4.0),
    ("elevated", 3.0),
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


async def _check_cooldown(region: str, alert_level: str) -> bool:
    """Check if we're still in cooldown for this region+level. Returns True if cooled down (ok to alert)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchval(
            """
            SELECT COUNT(*) FROM alerts
            WHERE LOWER(region) = LOWER($1)
              AND alert_level = $2
              AND created_at > NOW() - make_interval(mins => $3)
            """,
            region,
            alert_level,
            COOLDOWN_MINUTES,
        )
    return row == 0


async def _send_notifications(
    alert_level: str, region: str, risk_score: float, explanation: str = "", drivers: list | None = None
) -> list[dict[str, str]]:
    """Send real notifications where configured, simulate the rest."""
    actions = []

    # Teams: real delivery if enabled and webhook configured
    if settings.teams_enabled and settings.teams_webhook_url:
        try:
            from services.notifier import build_adaptive_card, send_teams_webhook

            card = build_adaptive_card(
                alert_level=alert_level,
                region=region,
                risk_score=risk_score,
                explanation=explanation,
                drivers=drivers,
                dashboard_url=settings.dashboard_url,
            )
            result = await send_teams_webhook(settings.teams_webhook_url, card)
            actions.append({
                "type": "teams",
                "target": settings.teams_webhook_url[:50],
                "label": "Microsoft Teams",
                "status": result["status"],
                "message": f"[QUIPU ALERT] {alert_level.upper()} risk for {region} (score: {risk_score}/5)",
            })
        except Exception as e:
            logger.error(f"Teams notification error: {e}")
            actions.append({
                "type": "teams",
                "target": settings.teams_webhook_url[:50],
                "label": "Microsoft Teams",
                "status": "failed",
                "message": str(e),
            })
    elif not settings.teams_enabled:
        logger.debug("Teams notifications disabled via TEAMS_ENABLED=false")
    else:
        actions.append({
            "type": "teams",
            "target": "(not configured)",
            "label": "Microsoft Teams",
            "status": "simulated",
            "message": f"[QUIPU ALERT] {alert_level.upper()} risk for {region} (score: {risk_score}/5)",
        })

    # Bluesky: real delivery if enabled and credentials configured
    if settings.bluesky_notifications_enabled and settings.bluesky_handle and settings.bluesky_app_password:
        try:
            from services.notifier import post_to_bluesky

            level_es = {"elevated": "ELEVADO", "high": "ALTO", "critical": "CRITICO"}.get(alert_level, alert_level.upper())
            # Build driver summary
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
            result = await post_to_bluesky(settings.bluesky_handle, settings.bluesky_app_password, text)
            actions.append({
                "type": "bluesky",
                "target": settings.bluesky_handle,
                "label": "Bluesky",
                "status": result["status"],
                "message": text[:200],
            })
        except Exception as e:
            logger.error(f"Bluesky notification error: {e}")
            actions.append({
                "type": "bluesky",
                "target": settings.bluesky_handle,
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


async def evaluate_and_alert(assessment: Any) -> dict[str, Any] | None:
    """Evaluate a risk assessment and trigger alerts if thresholds are exceeded.

    Returns alert info dict if an alert was triggered, None otherwise.
    """
    alert_level = _classify_alert_level(assessment.risk_score)
    if not alert_level:
        return None

    # Check cooldown
    if not await _check_cooldown(assessment.region, alert_level):
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
    )

    # Persist alert
    drivers_json = json.dumps(assessment.drivers) if assessment.drivers else None
    actions_json = json.dumps(actions)

    pool = await get_pool()
    async with pool.acquire() as conn:
        alert_id = await conn.fetchval(
            """
            INSERT INTO alerts (region, alert_level, risk_score, risk_level, explanation, drivers, actions_taken)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            assessment.region,
            alert_level,
            assessment.risk_score,
            assessment.risk_level,
            assessment.explanation,
            drivers_json,
            actions_json,
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

    # Broadcast via SSE
    await sse_manager.broadcast("alert", alert_data)

    logger.warning(
        f"ALERT TRIGGERED: {alert_level.upper()} for {assessment.region} "
        f"(risk_score={assessment.risk_score})"
    )

    return alert_data
