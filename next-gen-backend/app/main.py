# app/main.py

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.cameras import router as cameras_router
from app.api.endpoints import router as core_router
from app.api.live import router as live_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.models import Base
from app.db.session import engine
from app.middleware.request_context import RequestContextMiddleware
from app.services import runtime
from app.streaming.broadcaster import broadcaster

configure_logging()

logger = logging.getLogger("nexgen.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    # Models load here, before any camera thread exists, so every pipeline
    # shares one copy.
    runtime.init_runtime()

    # Camera threads publish from outside the event loop, so the broadcaster
    # needs a handle on the running loop before the first stream starts.
    broadcaster.bind_loop(asyncio.get_running_loop())

    manager = runtime.get_stream_manager()

    if manager is not None:
        manager.start_enabled_cameras()

    logger.info("NexGen live surveillance backend ready.")

    try:
        yield
    finally:
        # Stops capture/analyzer threads and flushes any still-open events.
        runtime.shutdown_runtime()
        logger.info("NexGen backend shut down.")


app = FastAPI(
    title="NexGen Surveillance Backend",
    description=(
        "Live multi-camera RTSP surveillance: face recognition, weapon "
        "detection, event tracking and real-time alerting."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        ["*"]
        if settings.cors_origins.strip() == "*"
        else [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestContextMiddleware)

app.include_router(core_router)
app.include_router(cameras_router)
app.include_router(live_router)


@app.get("/")
def root():
    return {
        "message": "NexGen Surveillance Backend",
        "mode": "live_multi_camera",
        "docs": "/docs",
        "health": "/api/v1/health",
        "cameras": "/api/v1/cameras",
        "live_websocket": "/api/v1/ws/live",
    }
