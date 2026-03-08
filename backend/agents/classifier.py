"""Keyword-based query classifier for dynamic agent selection."""

import re
from dataclasses import dataclass, field


@dataclass
class ClassificationResult:
    agents: list[str] = field(default_factory=list)
    reasoning: str = ""


# Keyword → agent mapping
KEYWORD_AGENTS: dict[str, list[str]] = {
    # Emergency / seismic
    "earthquake": ["EmergencyMonitor"],
    "sismo": ["EmergencyMonitor"],
    "terremoto": ["EmergencyMonitor"],
    "quake": ["EmergencyMonitor"],
    "tsunami": ["EmergencyMonitor"],
    "volcano": ["EmergencyMonitor"],
    "volcán": ["EmergencyMonitor"],
    "eruption": ["EmergencyMonitor"],
    "erupción": ["EmergencyMonitor"],
    "flood": ["EmergencyMonitor"],
    "inundación": ["EmergencyMonitor"],
    "cyclone": ["EmergencyMonitor"],
    "hurricane": ["EmergencyMonitor"],
    "huracán": ["EmergencyMonitor"],
    "storm": ["EmergencyMonitor"],
    "tormenta": ["EmergencyMonitor"],
    "drought": ["EmergencyMonitor"],
    "sequía": ["EmergencyMonitor"],
    "landslide": ["EmergencyMonitor", "WeatherAgent"],
    "disaster": ["EmergencyMonitor"],
    "desastre": ["EmergencyMonitor"],
    "alert": ["EmergencyMonitor"],
    "alerta": ["EmergencyMonitor"],
    # Fire
    "fire": ["FireMonitorAgent"],
    "incendio": ["FireMonitorAgent"],
    "wildfire": ["FireMonitorAgent"],
    "hotspot": ["FireMonitorAgent"],
    "burn": ["FireMonitorAgent"],
    "firms": ["FireMonitorAgent"],
    # Social / news
    "news": ["SocialNewsAgent"],
    "noticias": ["SocialNewsAgent"],
    "media": ["SocialNewsAgent"],
    "social": ["SocialNewsAgent"],
    "bluesky": ["SocialNewsAgent"],
    "report": ["SocialNewsAgent"],
    "informe": ["SocialNewsAgent"],
    "reliefweb": ["SocialNewsAgent"],
    "humanitarian": ["SocialNewsAgent"],
    "humanitario": ["SocialNewsAgent"],
    # Weather / rainfall
    "weather": ["WeatherAgent"],
    "rain": ["WeatherAgent"],
    "rainfall": ["WeatherAgent"],
    "lluvia": ["WeatherAgent"],
    "precipitation": ["WeatherAgent"],
    "huaico": ["WeatherAgent", "EmergencyMonitor"],
    "deslizamiento": ["WeatherAgent", "EmergencyMonitor"],
    "flood risk": ["WeatherAgent", "EmergencyMonitor"],
    # Notification
    "notify": ["NotificationAgent"],
    "notification": ["NotificationAgent"],
    "notificar": ["NotificationAgent"],
    "teams": ["NotificationAgent"],
    "send alert": ["NotificationAgent"],
    "enviar": ["NotificationAgent"],
    "communicate": ["NotificationAgent"],
    "avisar": ["NotificationAgent"],
    "alert authorities": ["NotificationAgent"],
    # Analysis
    "analysis": ["AnalysisAgent"],
    "análisis": ["AnalysisAgent"],
    "statistics": ["AnalysisAgent"],
    "trend": ["AnalysisAgent"],
    "risk": ["AnalysisAgent"],
    "riesgo": ["AnalysisAgent"],
    "sitrep": ["AnalysisAgent"],
    "situation report": ["AnalysisAgent"],
    "getting worse": ["AnalysisAgent"],
    "increasing": ["AnalysisAgent"],
    "escalating": ["AnalysisAgent"],
    "historical": ["AnalysisAgent"],
    "empeorando": ["AnalysisAgent"],
    "decreasing": ["AnalysisAgent"],
}

# Broad queries that should activate all agents
BROAD_KEYWORDS = [
    "what's happening", "qué está pasando", "overview", "resumen",
    "summary", "everything", "all", "status", "general",
    "how is", "cómo está", "situation", "situación", "monitor",
]

# Agents activated for broad "what's happening" queries
# NotificationAgent excluded — only activates on explicit send/notify requests
ALL_AGENTS = ["EmergencyMonitor", "SocialNewsAgent", "FireMonitorAgent", "AnalysisAgent", "WeatherAgent"]
DEFAULT_AGENTS = ["EmergencyMonitor", "AnalysisAgent"]


def classify_query(query: str) -> ClassificationResult:
    """Classify a user query to determine which agents should be activated."""
    query_lower = query.lower()

    # Check for broad queries first (word-boundary matching to avoid false positives like "all" in "rainfall")
    for keyword in BROAD_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', query_lower):
            return ClassificationResult(
                agents=list(ALL_AGENTS),
                reasoning=f"Broad query detected ('{keyword}') — activating all agents for comprehensive coverage",
            )

    # Collect matching agents from keywords
    matched_agents: set[str] = set()
    matched_keywords: list[str] = []

    for keyword, agents in KEYWORD_AGENTS.items():
        if keyword in query_lower:
            matched_agents.update(agents)
            matched_keywords.append(keyword)

    if not matched_agents:
        # Default fallback
        return ClassificationResult(
            agents=list(DEFAULT_AGENTS),
            reasoning="No specific keywords matched — using EmergencyMonitor + AnalysisAgent as default",
        )

    # Always include AnalysisAgent if any data agent is selected
    if matched_agents - {"AnalysisAgent"}:
        matched_agents.add("AnalysisAgent")

    # Sort for consistent ordering
    agent_order = {a: i for i, a in enumerate(ALL_AGENTS)}
    sorted_agents = sorted(matched_agents, key=lambda a: agent_order.get(a, 99))

    return ClassificationResult(
        agents=sorted_agents,
        reasoning=f"Keywords [{', '.join(matched_keywords)}] → selected {', '.join(sorted_agents)}",
    )
