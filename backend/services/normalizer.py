"""Normalizes raw API data from various sources into unified event schema."""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _parse_ts(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        # Handle millisecond epoch (USGS)
        if val.isdigit():
            return datetime.fromtimestamp(int(val) / 1000, tz=timezone.utc)
        # ISO format
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except (ValueError, OSError):
        return None


def _earthquake_severity(mag: float | None) -> int:
    if mag is None:
        return 1
    if mag >= 7.0:
        return 5
    if mag >= 6.0:
        return 4
    if mag >= 4.5:
        return 3
    if mag >= 3.0:
        return 2
    return 1


def _gdacs_severity(alert_level: str) -> int:
    return {"Red": 5, "Orange": 4, "Green": 2}.get(alert_level, 1)


def normalize_usgs_earthquake(feature: dict[str, Any]) -> dict[str, Any] | None:
    props = feature.get("properties", {})
    geom = feature.get("geometry", {})
    coords = geom.get("coordinates", [])
    if len(coords) < 2:
        return None
    lon, lat = coords[0], coords[1]
    mag = props.get("mag")
    eq_id = feature.get("id", "")
    return {
        "external_id": f"usgs_{eq_id}",
        "source": "usgs",
        "event_type": "earthquake",
        "title": props.get("title", f"M{mag} Earthquake"),
        "description": props.get("place", ""),
        "severity": _earthquake_severity(mag),
        "magnitude": mag,
        "lon": lon,
        "lat": lat,
        "started_at": _parse_ts(str(props.get("time", ""))),
        "raw_data": props,
    }


def normalize_gdacs_event(entry: dict[str, Any]) -> dict[str, Any] | None:
    try:
        # GDACS provides coords as "geo:point" = "lat lon" (space-separated)
        geo_point = entry.get("geo:point", "")
        if geo_point and geo_point.strip():
            parts = geo_point.strip().split()
            if len(parts) >= 2:
                lat = float(parts[0])
                lon = float(parts[1])
            else:
                lat = float(entry.get("geo:lat", 0))
                lon = float(entry.get("geo:long", 0))
        else:
            lat = float(entry.get("geo:lat", 0))
            lon = float(entry.get("geo:long", 0))
        # Skip events at (0,0) — means coordinates were not parsed
        if lat == 0 and lon == 0:
            return None
    except (ValueError, TypeError):
        return None

    event_type_map = {
        "EQ": "earthquake",
        "TC": "cyclone",
        "FL": "flood",
        "VO": "volcano",
        "WF": "wildfire",
        "DR": "drought",
    }
    gdacs_type = entry.get("gdacs:eventtype", "")
    alert_level = entry.get("gdacs:alertlevel", "Green")

    return {
        "external_id": f"gdacs_{gdacs_type}_{entry.get('gdacs:eventid', '')}",
        "source": "gdacs",
        "event_type": event_type_map.get(gdacs_type, gdacs_type.lower()),
        "title": entry.get("title", "GDACS Alert"),
        "description": entry.get("description", ""),
        "severity": _gdacs_severity(alert_level),
        "magnitude": None,
        "lon": lon,
        "lat": lat,
        "started_at": _parse_ts(entry.get("gdacs:fromdate")),
        "raw_data": entry,
    }


def normalize_eonet_event(event: dict[str, Any]) -> dict[str, Any] | None:
    geometries = event.get("geometry", event.get("geometries", []))
    if not geometries:
        return None

    # Use the latest geometry
    latest = geometries[-1] if isinstance(geometries, list) else geometries
    coords = latest.get("coordinates", [])
    if not coords or len(coords) < 2:
        return None

    lon, lat = coords[0], coords[1]

    categories = event.get("categories", [])
    category = categories[0].get("title", "unknown").lower() if categories else "unknown"

    # Map EONET categories
    type_map = {
        "wildfires": "wildfire",
        "severe storms": "storm",
        "volcanoes": "volcano",
        "floods": "flood",
        "earthquakes": "earthquake",
        "sea and lake ice": "ice",
        "drought": "drought",
        "landslides": "landslide",
    }

    return {
        "external_id": f"eonet_{event.get('id', '')}",
        "source": "eonet",
        "event_type": type_map.get(category, category),
        "title": event.get("title", "EONET Event"),
        "description": event.get("description") or "",
        "severity": 3,  # EONET doesn't provide severity; default to moderate
        "magnitude": None,
        "lon": lon,
        "lat": lat,
        "started_at": _parse_ts(latest.get("date")),
        "raw_data": event,
    }


def normalize_firms_fire(fire: dict[str, Any]) -> dict[str, Any] | None:
    try:
        lat = float(fire.get("latitude", 0))
        lon = float(fire.get("longitude", 0))
    except (ValueError, TypeError):
        return None

    confidence = fire.get("confidence", "")
    if isinstance(confidence, str):
        sev = {"high": 4, "nominal": 3, "low": 2}.get(confidence.lower(), 2)
    else:
        sev = 4 if int(confidence) >= 80 else 3 if int(confidence) >= 50 else 2

    acq_date = fire.get("acq_date", "")
    acq_time = fire.get("acq_time", "0000")
    fire_id = f"{lat:.3f}_{lon:.3f}_{acq_date}"

    started = None
    if acq_date:
        try:
            started = datetime.strptime(
                f"{acq_date} {acq_time}", "%Y-%m-%d %H%M"
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return {
        "external_id": f"firms_{fire_id}",
        "source": "firms",
        "event_type": "wildfire",
        "title": f"Active Fire ({fire.get('instrument', 'VIIRS')})",
        "description": f"Brightness: {fire.get('bright_ti4', 'N/A')}K, FRP: {fire.get('frp', 'N/A')} MW",
        "severity": sev,
        "magnitude": float(fire["frp"]) if fire.get("frp") else None,
        "lon": lon,
        "lat": lat,
        "started_at": started,
        "raw_data": fire,
    }
