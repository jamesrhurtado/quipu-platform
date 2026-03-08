"""Weather monitoring tools — rainfall anomaly detection via Open-Meteo."""

import json
from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx

from agent_framework import tool
from agents.scoring import wrap_tool_result


@tool
async def check_rainfall_anomaly(
    lat: Annotated[float, "Latitude of the location to check"],
    lon: Annotated[float, "Longitude of the location to check"],
    region_name: Annotated[str, "Human-readable region name (e.g. 'Cusco, Peru')"],
    days_back: Annotated[int, "Number of recent days to analyze (1-14)"] = 7,
) -> str:
    """Check rainfall anomaly for a location by comparing recent precipitation against the 5-year historical average for the same calendar window."""
    now = datetime.now(timezone.utc)

    # Step 1: Fetch recent precipitation from Open-Meteo Forecast API
    # Use past_days param only — do NOT combine with start_date/end_date (causes 400)
    recent_mm = 0.0
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "precipitation_sum",
                    "past_days": days_back,
                    "forecast_days": 1,
                    "timezone": "UTC",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            daily = data.get("daily", {})
            precip_values = daily.get("precipitation_sum", [])
            recent_mm = sum(v for v in precip_values if v is not None)
    except Exception as e:
        return wrap_tool_result(
            {"error": f"Open-Meteo forecast API failed: {e}", "region": region_name},
            source="Open-Meteo",
            timestamps=[],
        )

    # Step 2: Fetch historical average from Open-Meteo Historical Weather API
    # Average the same calendar window over the past 5 years
    historical_totals = []
    try:
        async with httpx.AsyncClient() as client:
            for years_ago in range(1, 6):
                hist_end = now.replace(year=now.year - years_ago)
                hist_start = hist_end - timedelta(days=days_back)
                resp = await client.get(
                    "https://archive-api.open-meteo.com/v1/archive",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "daily": "precipitation_sum",
                        "start_date": hist_start.strftime("%Y-%m-%d"),
                        "end_date": hist_end.strftime("%Y-%m-%d"),
                        "timezone": "UTC",
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                daily = data.get("daily", {})
                vals = daily.get("precipitation_sum", [])
                total = sum(v for v in vals if v is not None)
                historical_totals.append(total)
    except Exception as e:
        return wrap_tool_result(
            {
                "error": f"Open-Meteo historical API failed: {e}",
                "region": region_name,
                "recent_precipitation_mm": round(recent_mm, 1),
            },
            source="Open-Meteo",
            timestamps=[now.isoformat()],
        )

    # Step 3: Compute anomaly
    historical_avg = sum(historical_totals) / len(historical_totals) if historical_totals else 0.0
    if historical_avg > 0:
        anomaly_pct = ((recent_mm - historical_avg) / historical_avg) * 100
    else:
        anomaly_pct = 100.0 if recent_mm > 0 else 0.0

    # Classify
    abs_anomaly = abs(anomaly_pct) if anomaly_pct > 0 else 0
    if abs_anomaly > 150:
        classification = "Extreme"
    elif abs_anomaly > 80:
        classification = "Heavy"
    elif abs_anomaly > 30:
        classification = "Above Normal"
    else:
        classification = "Normal"

    # Landslide risk flag
    landslide_risk = classification in ("Heavy", "Extreme")

    return wrap_tool_result(
        {
            "region": region_name,
            "period_days": days_back,
            "recent_precipitation_mm": round(recent_mm, 1),
            "historical_avg_mm": round(historical_avg, 1),
            "anomaly_pct": round(anomaly_pct, 1),
            "classification": classification,
            "landslide_risk_flag": landslide_risk,
            "note": (
                f"Rainfall in {region_name} over the last {days_back} days: {recent_mm:.1f}mm "
                f"vs historical average {historical_avg:.1f}mm ({anomaly_pct:+.0f}%). "
                f"Classification: {classification}."
                + (" LANDSLIDE RISK elevated due to heavy rainfall." if landslide_risk else "")
            ),
        },
        source="Open-Meteo",
        timestamps=[now.isoformat()],
    )
