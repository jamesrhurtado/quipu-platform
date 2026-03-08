"""Risk escalation scoring engine — composite risk assessment computation."""

from dataclasses import dataclass, field


COMPONENT_LABELS = {
    "event_severity": "Event Severity",
    "fire_density": "Fire Activity",
    "media_spike": "Media Coverage",
    "confidence": "Data Confidence",
}

COMPONENT_WEIGHTS = {
    "event_severity": 0.35,
    "fire_density": 0.20,
    "media_spike": 0.20,
    "confidence": 0.25,
}


def _interpret_event_severity(value: float) -> str:
    if value >= 4.5:
        return "Major disaster-level events detected"
    if value >= 3.5:
        return "Significant events with regional impact"
    if value >= 2.5:
        return "Moderate events with localized impact"
    return "Routine activity levels"


def _interpret_fire_density(value: float, fire_count: int) -> str:
    if value >= 4.0:
        return f"Extreme fire activity ({fire_count} detections, well above baseline)"
    if value >= 3.0:
        return f"Elevated fire activity ({fire_count} detections, above baseline)"
    if value >= 2.0:
        return f"Moderate fire activity ({fire_count} detections)"
    return "Minimal fire activity"


def _interpret_media_spike(value: float, article_count: int) -> str:
    if value >= 4.0:
        return f"Major media surge ({article_count} articles, indicating widespread attention)"
    if value >= 3.0:
        return f"Significant media coverage ({article_count} articles, above normal)"
    if value >= 2.0:
        return f"Moderate media interest ({article_count} articles)"
    return "Normal media activity"


def _interpret_confidence(value: float, avg_confidence: float) -> str:
    if avg_confidence >= 0.8:
        return "High data confidence — multiple reliable sources corroborate"
    if avg_confidence >= 0.6:
        return "Moderate confidence — primary sources available"
    if avg_confidence >= 0.4:
        return "Limited confidence — relying on lower-reliability sources"
    return "Low confidence — sparse or unreliable data"


@dataclass
class RiskAssessment:
    region: str
    risk_score: float
    risk_level: str
    components: dict[str, float] = field(default_factory=dict)
    explanation: str = ""
    drivers: list[dict] = field(default_factory=list)
    component_analysis: dict[str, dict] = field(default_factory=dict)


# Baseline for media spike normalization
MEDIA_BASELINE = 5  # "normal" number of articles for a region
FIRE_BASELINE = 10  # "normal" fire count


def compute_risk(
    region: str,
    max_severity: float = 1.0,
    fire_count: int = 0,
    news_article_count: int = 0,
    avg_confidence: float = 0.5,
) -> RiskAssessment:
    """Compute a composite risk score for a region.

    Risk formula:
        risk_score = (
            0.35 * event_severity_component +
            0.20 * fire_density_component +
            0.20 * media_spike_component +
            0.25 * confidence_component
        )

    All components are normalized to 1-5 scale.
    """
    # Component 1: Event severity (already 1-5 scale)
    event_severity_component = max(1.0, min(5.0, max_severity))

    # Component 2: Fire density (normalized: 0 fires=1, FIRE_BASELINE+=3, 3x baseline=5)
    if fire_count <= 0:
        fire_density_component = 1.0
    else:
        normalized = fire_count / FIRE_BASELINE
        fire_density_component = min(5.0, 1.0 + normalized * 4.0 / 3.0)

    # Component 3: Media spike (normalized against baseline)
    if news_article_count <= 0:
        media_spike_component = 1.0
    else:
        spike_ratio = news_article_count / MEDIA_BASELINE
        media_spike_component = min(5.0, 1.0 + spike_ratio * 4.0 / 3.0)

    # Component 4: Confidence (0-1 scaled to 1-5)
    confidence_component = 1.0 + avg_confidence * 4.0

    # Weighted composite
    risk_score = (
        0.35 * event_severity_component
        + 0.20 * fire_density_component
        + 0.20 * media_spike_component
        + 0.25 * confidence_component
    )
    risk_score = round(max(1.0, min(5.0, risk_score)), 1)

    # Classify level
    if risk_score >= 4.0:
        risk_level = "Critical"
    elif risk_score >= 3.0:
        risk_level = "Elevated"
    else:
        risk_level = "Normal"

    components = {
        "event_severity": round(event_severity_component, 2),
        "fire_density": round(fire_density_component, 2),
        "media_spike": round(media_spike_component, 2),
        "confidence": round(confidence_component, 2),
    }

    # Build component analysis with interpretations
    component_values = {
        "event_severity": event_severity_component,
        "fire_density": fire_density_component,
        "media_spike": media_spike_component,
        "confidence": confidence_component,
    }
    interpretations = {
        "event_severity": _interpret_event_severity(event_severity_component),
        "fire_density": _interpret_fire_density(fire_density_component, fire_count),
        "media_spike": _interpret_media_spike(media_spike_component, news_article_count),
        "confidence": _interpret_confidence(confidence_component, avg_confidence),
    }

    component_analysis = {}
    for key in components:
        weight = COMPONENT_WEIGHTS[key]
        value = component_values[key]
        component_analysis[key] = {
            "label": COMPONENT_LABELS[key],
            "value": round(value, 2),
            "weight": weight,
            "weighted_contribution": round(value * weight, 2),
            "interpretation": interpretations[key],
        }

    # Identify primary risk drivers (components above 3.0)
    drivers = []
    for key, value in component_values.items():
        if value >= 3.0:
            drivers.append({
                "component": key,
                "label": COMPONENT_LABELS[key],
                "value": round(value, 2),
                "reason": interpretations[key],
            })
    drivers.sort(key=lambda d: d["value"], reverse=True)

    parts = []
    if event_severity_component >= 4:
        parts.append(f"high event severity ({event_severity_component}/5)")
    if fire_density_component >= 3:
        parts.append(f"elevated fire activity ({fire_count} detections)")
    if media_spike_component >= 3:
        parts.append(f"significant media coverage ({news_article_count} articles)")
    if not parts:
        parts.append("routine monitoring levels across all indicators")

    explanation = (
        f"Risk level {risk_level} ({risk_score}/5) for {region}: "
        + "; ".join(parts)
        + f". Data confidence: {avg_confidence:.0%}."
    )

    return RiskAssessment(
        region=region,
        risk_score=risk_score,
        risk_level=risk_level,
        components=components,
        explanation=explanation,
        drivers=drivers,
        component_analysis=component_analysis,
    )
