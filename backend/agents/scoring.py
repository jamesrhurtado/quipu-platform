"""Source reliability weights and scoring helpers for agent tool results."""

import json
from datetime import datetime, timezone

SOURCE_WEIGHTS: dict[str, float] = {
    "USGS": 1.0,
    "GDACS": 0.9,
    "NASA EONET": 0.85,
    "NASA FIRMS": 0.85,
    "GDELT": 0.6,
    "Bluesky": 0.4,
    "ReliefWeb": 0.95,
    "local database": 0.9,
}

# Maximum age (hours) before freshness decays to 0
DEFAULT_MAX_AGE_HOURS = 168  # 7 days


def _compute_freshness(timestamps: list[str | None], max_age_hours: float = DEFAULT_MAX_AGE_HOURS) -> float:
    """Compute freshness score (0.0-1.0) based on average timestamp age.

    Linear decay from 1.0 (now) to 0.0 (max_age_hours old).
    """
    now = datetime.now(timezone.utc)
    valid_ages: list[float] = []

    for ts in timestamps:
        if not ts:
            continue
        try:
            # Handle various timestamp formats
            if isinstance(ts, (int, float)):
                # Unix timestamp in milliseconds (USGS)
                dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            else:
                ts_str = str(ts).strip()
                # Try ISO format first
                for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
                            "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
                            "%Y%m%dT%H%M%S"):
                    try:
                        dt = datetime.strptime(ts_str, fmt)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
                else:
                    continue

            age_hours = (now - dt).total_seconds() / 3600
            valid_ages.append(max(0, age_hours))
        except (ValueError, TypeError, OSError):
            continue

    if not valid_ages:
        return 0.5  # Default when no valid timestamps

    avg_age = sum(valid_ages) / len(valid_ages)
    freshness = max(0.0, 1.0 - (avg_age / max_age_hours))
    return round(freshness, 3)


def wrap_tool_result(
    data: dict,
    source: str,
    timestamps: list[str | None] | None = None,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
) -> str:
    """Wrap a tool result dict with reliability and freshness scores.

    Returns a JSON string containing the original data plus scoring metadata.
    """
    reliability = SOURCE_WEIGHTS.get(source, 0.5)
    freshness = _compute_freshness(timestamps or [], max_age_hours) if timestamps else 0.5

    return json.dumps({
        **data,
        "reliability_score": reliability,
        "freshness_score": freshness,
        "source": source,
    })
