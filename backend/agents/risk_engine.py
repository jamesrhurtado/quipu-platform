"""Risk escalation scoring engine — composite risk assessment computation."""

from dataclasses import dataclass, field


@dataclass
class RiskAssessment:
    region: str
    risk_score: float
    risk_level: str
    components: dict[str, float] = field(default_factory=dict)
    explanation: str = ""


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
    )
