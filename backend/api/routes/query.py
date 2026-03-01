"""Query endpoint that triggers the Magentic multi-agent workflow."""

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.definitions import run_agent_query

logger = logging.getLogger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    query: str


@router.post("/api/query")
async def handle_query(req: QueryRequest):
    """Process a natural language query through the multi-agent system.

    Returns a streaming response with agent status updates and the final answer.
    """

    async def generate():
        try:
            async for chunk in run_agent_query(req.query):
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
