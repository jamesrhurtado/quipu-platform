"""Agent definitions and Magentic orchestration setup."""

import asyncio
import json
import logging
import os
import re
import time
from collections.abc import AsyncIterator
from typing import Any

# Semantic Kernel validates its own AzureOpenAISettings from os.environ,
# but pydantic-settings only loads .env into the model — not into the process env.
# Bridge the gap before any SK imports touch settings validation.
from config import settings as _settings

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", _settings.azure_openai_endpoint)
os.environ.setdefault("AZURE_OPENAI_API_KEY", _settings.azure_openai_api_key)

from semantic_kernel.agents import (
    ChatCompletionAgent,
    MagenticOrchestration,
    StandardMagenticManager,
)
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents import ChatMessageContent

from agents.classifier import classify_query
from agents.instructions import (
    ANALYSIS_INSTRUCTIONS,
    EMERGENCY_MONITOR_INSTRUCTIONS,
    FIRE_MONITOR_INSTRUCTIONS,
    MANAGER_INSTRUCTIONS,
    SOCIAL_NEWS_INSTRUCTIONS,
)
from agents.tools.analysis import AnalysisPlugin
from agents.tools.emergency import EmergencyPlugin
from agents.tools.satellite import FireMonitorPlugin
from agents.tools.social import SocialNewsPlugin
from config import settings

logger = logging.getLogger(__name__)

# Agent definitions registry
AGENT_DEFS: dict[str, dict[str, Any]] = {
    "EmergencyMonitor": {
        "description": "Monitors real-time earthquake, flood, cyclone, volcano, and disaster alerts from USGS, GDACS, NASA EONET, and local database.",
        "instructions": EMERGENCY_MONITOR_INSTRUCTIONS,
        "deployment": "mini",
        "plugin_class": EmergencyPlugin,
    },
    "SocialNewsAgent": {
        "description": "Searches news articles via GDELT, social media via Bluesky, and humanitarian reports via ReliefWeb for disaster coverage.",
        "instructions": SOCIAL_NEWS_INSTRUCTIONS,
        "deployment": "mini",
        "plugin_class": SocialNewsPlugin,
    },
    "FireMonitorAgent": {
        "description": "Queries NASA FIRMS for active fire detections and hotspot analysis.",
        "instructions": FIRE_MONITOR_INSTRUCTIONS,
        "deployment": "mini",
        "plugin_class": FireMonitorPlugin,
    },
    "AnalysisAgent": {
        "description": "Analyzes aggregated disaster data from the PostGIS database, computes risk assessments, and generates structured situation reports.",
        "instructions": ANALYSIS_INSTRUCTIONS,
        "deployment": "full",
        "plugin_class": AnalysisPlugin,
    },
}


def _make_service(deployment: str) -> AzureChatCompletion:
    """Create an Azure OpenAI chat completion service."""
    return AzureChatCompletion(
        deployment_name=deployment,
        endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )


def _build_agents(selected_names: list[str] | None = None) -> tuple[list[ChatCompletionAgent], AzureChatCompletion]:
    """Build agents filtered by selected_names. Returns agents + manager service."""
    mini = settings.azure_openai_gpt4o_mini_deployment
    full = settings.azure_openai_gpt4o_deployment
    deployment_map = {"mini": mini, "full": full}

    names = selected_names or list(AGENT_DEFS.keys())
    agents = []
    for name in names:
        defn = AGENT_DEFS.get(name)
        if not defn:
            continue
        agents.append(ChatCompletionAgent(
            name=name,
            description=defn["description"],
            instructions=defn["instructions"],
            service=_make_service(deployment_map[defn["deployment"]]),
            plugins=[defn["plugin_class"]()],
        ))

    manager_service = _make_service(full)
    return agents, manager_service


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
    agents, manager_service = _build_agents(classification.agents)

    # Collect agent responses via callback
    response_queue: asyncio.Queue[dict] = asyncio.Queue()

    def on_agent_response(message: ChatMessageContent) -> None:
        agent_name = message.name or "unknown"
        content = message.content or ""
        response_queue.put_nowait({
            "type": "agent_response",
            "agent": agent_name,
            "content": content,
        })

    orchestration = MagenticOrchestration(
        members=agents,
        manager=StandardMagenticManager(
            chat_completion_service=manager_service,
        ),
        agent_response_callback=on_agent_response,
    )

    runtime = InProcessRuntime()
    runtime.start()

    try:
        yield {"type": "status", "agent": "manager", "message": "Delegating to specialist agents..."}
        yield make_timeline_step("manager", "delegate", f"Delegating to {len(agents)} specialist agents")

        orchestration_result = await orchestration.invoke(
            task=f"{MANAGER_INSTRUCTIONS}\n\nUser query: {query}",
            runtime=runtime,
        )

        result_task = asyncio.create_task(orchestration_result.get())

        # Track which agents have responded for timeline
        agents_seen: set[str] = set()

        while not result_task.done():
            try:
                msg = await asyncio.wait_for(response_queue.get(), timeout=1.0)
                yield msg
                # Emit timeline step for first response from each agent
                agent_name = msg.get("agent", "unknown")
                if agent_name not in agents_seen:
                    agents_seen.add(agent_name)
                    content_preview = (msg.get("content", "") or "")[:80]
                    yield make_timeline_step(agent_name, "response", content_preview)
            except asyncio.TimeoutError:
                continue

        final = await result_task
        final_content = final.content if hasattr(final, "content") else str(final)

        # Drain remaining queued messages
        while not response_queue.empty():
            msg = response_queue.get_nowait()
            yield msg
            agent_name = msg.get("agent", "unknown")
            if agent_name not in agents_seen:
                agents_seen.add(agent_name)
                content_preview = (msg.get("content", "") or "")[:80]
                yield make_timeline_step(agent_name, "response", content_preview)

        # Extract structured data from final answer
        narrative, structured = _extract_structured_data(final_content)

        yield make_timeline_step("manager", "synthesize", "Final intelligence report ready")

        final_event: dict[str, Any] = {
            "type": "final_answer",
            "content": narrative,
        }
        if structured:
            # Spread structured fields into the final answer event
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

        yield final_event

    except Exception as e:
        logger.error(f"Agent orchestration error: {e}", exc_info=True)
        yield make_timeline_step("manager", "error", str(e))
        yield {
            "type": "error",
            "message": f"Agent error: {str(e)}",
        }
    finally:
        await runtime.stop_when_idle()
