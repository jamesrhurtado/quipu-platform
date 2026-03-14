"""Agent definitions and Magentic orchestration setup using Microsoft Agent Framework."""

import json
import logging
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from agent_framework import Agent, AgentResponseUpdate, Message, WorkflowEvent
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework.orchestrations import MagenticBuilder

from agents.classifier import classify_query
from agents.instructions import (
    ANALYSIS_INSTRUCTIONS,
    EMERGENCY_MONITOR_INSTRUCTIONS,
    FIRE_MONITOR_INSTRUCTIONS,
    MANAGER_INSTRUCTIONS,
    NOTIFICATION_INSTRUCTIONS,
    SOCIAL_NEWS_INSTRUCTIONS,
    WEATHER_INSTRUCTIONS,
)
from agents.tools.analysis import (
    compute_risk_assessment,
    generate_situation_report,
    get_risk_trend,
    query_event_database,
)
from agents.tools.emergency import (
    query_cached_events,
    query_earthquakes,
    query_eonet_events,
    query_gdacs_alerts,
)
from agents.tools.notification import get_notification_history, post_bluesky_alert, send_teams_alert
from agents.tools.satellite import query_active_fires
from agents.tools.social import monitor_bluesky, search_news, search_reliefweb
from agents.tools.weather import check_rainfall_anomaly
from config import settings

logger = logging.getLogger(__name__)


def _make_chat_client(deployment: str) -> AzureOpenAIChatClient:
    """Create an Azure OpenAI chat client for the Agent Framework."""
    return AzureOpenAIChatClient(
        endpoint=settings.azure_openai_endpoint,
        deployment_name=deployment,
        api_key=settings.azure_openai_api_key,
    )


# Agent definitions registry
AGENT_DEFS: dict[str, dict[str, Any]] = {
    "EmergencyMonitor": {
        "description": "Monitors real-time earthquake, flood, cyclone, volcano, and disaster alerts from USGS, GDACS, NASA EONET, and local database.",
        "instructions": EMERGENCY_MONITOR_INSTRUCTIONS,
        "deployment": "mini",
        "tools": [query_earthquakes, query_gdacs_alerts, query_eonet_events, query_cached_events],
    },
    "SocialNewsAgent": {
        "description": "Searches news articles via GDELT, social media via Bluesky, and humanitarian reports via ReliefWeb for disaster coverage.",
        "instructions": SOCIAL_NEWS_INSTRUCTIONS,
        "deployment": "mini",
        "tools": [search_news, monitor_bluesky, search_reliefweb],
    },
    "FireMonitorAgent": {
        "description": "Queries NASA FIRMS for active fire detections and hotspot analysis.",
        "instructions": FIRE_MONITOR_INSTRUCTIONS,
        "deployment": "mini",
        "tools": [query_active_fires],
    },
    "AnalysisAgent": {
        "description": "Analyzes aggregated disaster data from the PostGIS database, computes risk assessments, generates situation reports, and analyzes risk trends.",
        "instructions": ANALYSIS_INSTRUCTIONS,
        "deployment": "full",
        "tools": [query_event_database, generate_situation_report, compute_risk_assessment, get_risk_trend],
    },
    "WeatherAgent": {
        "description": "Detects rainfall anomalies and weather-related disaster risks using Open-Meteo climate data. Flags landslide risk from heavy rainfall.",
        "instructions": WEATHER_INSTRUCTIONS,
        "deployment": "mini",
        "tools": [check_rainfall_anomaly],
    },
    "NotificationAgent": {
        "description": "Delivers alerts to Microsoft Teams (Adaptive Cards) and Bluesky (public advisories). Tracks notification delivery history.",
        "instructions": NOTIFICATION_INSTRUCTIONS,
        "deployment": "mini",
        "tools": [send_teams_alert, post_bluesky_alert, get_notification_history],
    },
}


def _build_agents(selected_names: list[str] | None = None) -> tuple[list[Agent], Agent]:
    """Build agents filtered by selected_names. Returns agents + manager agent."""
    mini = settings.azure_openai_gpt4o_mini_deployment
    full = settings.azure_openai_gpt4o_deployment
    deployment_map = {"mini": mini, "full": full}

    names = selected_names or list(AGENT_DEFS.keys())
    agents = []
    for name in names:
        defn = AGENT_DEFS.get(name)
        if not defn:
            continue
        agents.append(Agent(
            _make_chat_client(deployment_map[defn["deployment"]]),
            defn["instructions"],
            name=name,
            description=defn["description"],
            tools=defn["tools"],
        ))

    manager_agent = Agent(
        _make_chat_client(full),
        MANAGER_INSTRUCTIONS,
        name="Manager",
        description="Orchestrator that coordinates specialist disaster monitoring agents",
    )
    return agents, manager_agent


def _extract_structured_data(content: str) -> tuple[str, dict[str, Any] | None]:
    """Extract JSON structured data block from the final answer.

    Returns (clean_narrative, structured_data_or_None).
    """
    pattern = r"```json\s*\n(.*?)\n\s*```"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return content, None

    try:
        structured = json.loads(match.group(1))
        # Remove the JSON block from narrative
        narrative = content[:match.start()].rstrip() + content[match.end():].lstrip()
        return narrative.strip(), structured
    except json.JSONDecodeError:
        return content, None


async def run_agent_query(query: str) -> AsyncIterator[dict[str, Any]]:
    """Run a natural language query through the Magentic multi-agent workflow.

    Yields status updates, timeline events, and the final answer as dicts.
    """
    start_time = time.monotonic()
    step_counter = 0

    def elapsed_ms() -> int:
        return int((time.monotonic() - start_time) * 1000)

    def make_timeline_step(agent: str, action: str, message: str) -> dict:
        nonlocal step_counter
        step_counter += 1
        return {
            "type": "timeline_step",
            "step": step_counter,
            "agent": agent,
            "action": action,
            "message": message,
            "elapsed_ms": elapsed_ms(),
        }

    # Step 1: Classify query
    classification = classify_query(query)
    yield {
        "type": "classification",
        "agents": classification.agents,
        "reasoning": classification.reasoning,
    }
    yield make_timeline_step("manager", "classify", f"Selected agents: {', '.join(classification.agents)}")

    yield {"type": "status", "agent": "manager", "message": "Planning approach..."}

    # Step 2: Build only selected agents
    agents, manager_agent = _build_agents(classification.agents)

    yield {"type": "status", "agent": "manager", "message": "Delegating to specialist agents..."}
    yield make_timeline_step("manager", "delegate", f"Delegating to {len(agents)} specialist agents")

    # Build the Magentic workflow
    workflow = MagenticBuilder(
        participants=agents,
        manager_agent=manager_agent,
        max_round_count=6,
        max_stall_count=2,
    ).build()

    try:
        agents_seen: set[str] = set()
        final_content = ""

        async for event in workflow.run(f"{MANAGER_INSTRUCTIONS}\n\nUser query: {query}", stream=True):
            if event.type == "output" and isinstance(event.data, AgentResponseUpdate):
                # Intermediate agent response
                agent_name = event.executor_id or "unknown"
                content = event.data.text or ""

                yield {
                    "type": "agent_response",
                    "agent": agent_name,
                    "content": content,
                }

                if agent_name not in agents_seen:
                    agents_seen.add(agent_name)
                    content_preview = content[:80]
                    yield make_timeline_step(agent_name, "response", content_preview)

            elif event.type == "output":
                # Final output — extract messages
                data = event.data
                if isinstance(data, list) and data:
                    # List of Messages — take the last one
                    last = data[-1]
                    final_content = last.text if isinstance(last, Message) else str(last)
                elif isinstance(data, Message):
                    final_content = data.text
                else:
                    final_content = str(data)

        # Extract structured data from final answer
        narrative, structured = _extract_structured_data(final_content)

        yield make_timeline_step("manager", "synthesize", "Final intelligence report ready")

        final_event: dict[str, Any] = {
            "type": "final_answer",
            "content": narrative,
        }
        if structured:
            if "risk_assessment" in structured:
                final_event["risk_assessment"] = structured["risk_assessment"]
            if "source_breakdown" in structured:
                final_event["source_breakdown"] = structured["source_breakdown"]
            if "map_focus" in structured:
                final_event["map_focus"] = structured["map_focus"]
            if "recommendations" in structured:
                final_event["recommendations"] = structured["recommendations"]
            if "overall_confidence" in structured:
                final_event["overall_confidence"] = structured["overall_confidence"]
            # Phase 1: Risk drivers
            if "risk_drivers" in structured:
                final_event["risk_drivers"] = structured["risk_drivers"]
            # Phase 2: Trend data
            if "trend" in structured:
                final_event["trend"] = structured["trend"]

        yield final_event

    except Exception as e:
        logger.error(f"Agent orchestration error: {e}", exc_info=True)
        yield make_timeline_step("manager", "error", str(e))
        yield {
            "type": "error",
            "message": f"Agent error: {str(e)}",
        }
