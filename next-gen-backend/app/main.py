# app/main.py

import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.cameras import router as cameras_router
from app.api.discovery import router as discovery_router
from app.api.discovery import start_auto_discover
from app.api.endpoints import router as core_router
from app.api.live import router as live_router
from app.api.panic import router as panic_router
from app.api.site import router as site_router
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

    # Runs in the background: the API is usable while the network is scanned.
    start_auto_discover()

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

# localhost plus the private IPv4 ranges: the dashboard works from this
# machine or a phone on the same network, but an arbitrary website open in the
# operator's browser cannot read camera credentials off the API.
_LAN_ORIGIN_REGEX = (
    r"^https?://("
    r"localhost|127\.0\.0\.1|\[::1\]|"
    r"10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|"
    r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+"
    r")(:\d+)?$"
)

_cors = settings.cors_origins.strip()

if _cors in ("", "lan"):
    _cors_kwargs = {"allow_origin_regex": _LAN_ORIGIN_REGEX}
elif _cors == "*":
    _cors_kwargs = {"allow_origins": ["*"]}
else:
    _cors_kwargs = {
        "allow_origins": [o.strip() for o in _cors.split(",") if o.strip()]
    }

app.add_middleware(
    CORSMiddleware,
    allow_methods=["*"],
    allow_headers=["*"],
    **_cors_kwargs,
)

app.add_middleware(RequestContextMiddleware)

app.include_router(core_router)
app.include_router(cameras_router)
app.include_router(live_router)
app.include_router(discovery_router)
app.include_router(site_router)
app.include_router(panic_router)


_frontend_dist = Path(settings.frontend_dist_dir)
_serve_dashboard = (_frontend_dist / "index.html").is_file()


@app.get("/api/v1")
def root():
    return {
        "message": "NexGen Surveillance Backend",
        "mode": "live_multi_camera",
        "docs": "/docs",
        "health": "/api/v1/health",
        "cameras": "/api/v1/cameras",
        "live_websocket": "/api/v1/ws/live",
    }


if _serve_dashboard:
    # Single-process appliance mode: the built dashboard is served from the
    # same origin as the API, so one port is all a browser needs.
    import mimetypes

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    # Not in the Windows registry by default; without it the login photo is
    # served as a generic download type.
    mimetypes.add_type("image/webp", ".webp")

    app.mount(
        "/assets",
        StaticFiles(directory=_frontend_dist / "assets"),
        name="dashboard-assets",
    )

    @app.get("/{path:path}", include_in_schema=False)
    def dashboard(path: str):
        candidate = (_frontend_dist / path).resolve()

        if (
            path
            and _frontend_dist.resolve() in candidate.parents
            and candidate.is_file()
        ):
            return FileResponse(candidate)

        # Client-side routes (/cameras, /events, ...) all load the app shell.
        return FileResponse(_frontend_dist / "index.html")

else:

    @app.get("/")
    def root_redirect():
        return root()
