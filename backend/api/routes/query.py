"""Query endpoint that triggers the Magentic multi-agent workflow."""

import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.definitions import run_agent_query
from auth import TenantContext, get_tenant
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    query: str


@router.post("/api/query")
async def handle_query(
    req: QueryRequest,
    tenant: TenantContext = Depends(get_tenant),
):
    """Process a natural language query through the multi-agent system.

    Returns a streaming response with agent status updates and the final answer.
    """
    # Build tenant context prefix for the agent
    tenant_prefix = ""
    if settings.multi_tenant_enabled:
        tenant_prefix = (
            f"You are assisting {tenant.municipality}"
            f"{f' in {tenant.department}' if tenant.department else ''}, Peru. "
            f"Focus area bounding box: "
            f"lat [{tenant.bbox_min_lat}, {tenant.bbox_max_lat}], "
            f"lon [{tenant.bbox_min_lon}, {tenant.bbox_max_lon}]. "
            f"Prioritize information relevant to this region.\n\n"
        )

    # Store tenant org_id so agent tools can access it
    from agents.tools.analysis import _current_org_id
    _current_org_id.set(tenant.org_id if settings.multi_tenant_enabled else None)

    async def generate():
        try:
            async for chunk in run_agent_query(tenant_prefix + req.query):
                yield f"data: {json.dumps(chunk, default=str)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Agent query error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
