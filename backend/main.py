"""FastAPI application with lifespan management for poller and Bluesky buffer."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.alerts import router as alerts_router
from api.routes.events import router as events_router
from api.routes.query import router as query_router
from api.routes.risk import router as risk_router
from api.routes.stream import router as stream_router
from config import settings
from db import close_db, init_db
from services.bluesky_buffer import bluesky_buffer
from services.poller import start_polling

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Quipu backend...")
    await init_db()

    # Start background tasks
    poller_task = asyncio.create_task(start_polling())

    bluesky_task = None
    if settings.bluesky_enabled:
        logger.info("Bluesky buffer enabled, starting...")
        bluesky_task = asyncio.create_task(bluesky_buffer.start())
    else:
        logger.info("Bluesky buffer disabled (set BLUESKY_ENABLED=true to enable)")

    yield

    # Shutdown
    logger.info("Shutting down...")
    if bluesky_task:
        bluesky_buffer.stop()
        bluesky_task.cancel()
        try:
            await bluesky_task
        except asyncio.CancelledError:
            pass
    poller_task.cancel()
    try:
        await poller_task
    except asyncio.CancelledError:
        pass
    await close_db()


app = FastAPI(
    title="Quipu — Disaster & Climate Risk Monitor",
    description="Multi-agent AI system for disaster monitoring in Latin America",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(alerts_router)
app.include_router(events_router)
app.include_router(stream_router)
app.include_router(query_router)
app.include_router(risk_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "quipu"}
