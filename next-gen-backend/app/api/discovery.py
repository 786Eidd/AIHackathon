# app/api/discovery.py

"""
Plug-and-play camera onboarding.

`scan` lists what the box can see; `connect` turns a discovered device into
registered, running cameras. Sources that need no login (attached webcams,
phone camera apps) are registered directly. Recorders and IP cameras need a
login once, after which every channel that is actually delivering video is
added in one go.

The same code runs unattended at boot (`auto_discover`), which is what makes
the appliance come up already watching whatever it was plugged into.
"""

import logging
import threading
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.timeutil import redact_url
from app.db.models import Camera
from app.db.session import SessionLocal
from app.discovery import scanner
from app.services import runtime
from app.streaming.capture import webcam_index

logger = logging.getLogger("nexgen.api.discovery")

router = APIRouter(prefix="/api/v1", tags=["discovery"])

# One scan at a time: it opens webcams and a few hundred sockets.
_scan_lock = threading.Lock()
_last_scan: dict = {"devices": [], "scanned": False}


class ConnectRequest(BaseModel):
    kind: str = Field(pattern="^(rtsp|mjpeg|webcam)$")
    host: str = Field(default="", max_length=255)
    port: int = Field(default=554, ge=0, le=65535)
    username: str = Field(default="", max_length=128)
    password: str = Field(default="", max_length=128)
    label: Optional[str] = Field(default=None, max_length=200)


def _registered() -> List[tuple]:
    db = SessionLocal()

    try:
        return [(c.id, c.name, c.rtsp_url) for c in db.query(Camera).all()]
    finally:
        db.close()


def _host_port(url: str) -> Optional[tuple]:
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(url)
        return parts.hostname, parts.port
    except ValueError:
        return None


def _annotate(devices: List[dict]) -> List[dict]:
    """Marks which discovered sources are already registered cameras."""
    registered = _registered()

    webcams = {webcam_index(url) for _, _, url in registered} - {None}
    endpoints = {_host_port(url) for _, _, url in registered}

    annotated = []

    for device in devices:
        if device["kind"] == "webcam":
            added = device["port"] in webcams
        else:
            added = (device["host"], device["port"]) in endpoints

        annotated.append({**device, "already_added": added})

    return annotated


def run_scan() -> List[dict]:
    with _scan_lock:
        webcams_in_use = {
            webcam_index(url) for _, _, url in _registered()
        } - {None}

        devices = scanner.scan(webcams_in_use)

        _last_scan["devices"] = devices
        _last_scan["scanned"] = True

    return devices


def _register(name: str, url: str, location: Optional[str] = None) -> Optional[dict]:
    """Adds and starts one camera. Returns None if the URL is already known."""
    db = SessionLocal()

    try:
        if db.query(Camera).filter(Camera.rtsp_url == url).first() is not None:
            return None

        camera = Camera(
            id=f"cam_{uuid4().hex[:12]}",
            name=name,
            rtsp_url=url,
            location=location,
            enabled=True,
            status="offline",
        )

        db.add(camera)
        db.commit()

        camera_id = camera.id

    finally:
        db.close()

    manager = runtime.get_stream_manager()
    started = False
    warning = None

    if manager is not None:
        try:
            started = manager.start_camera(camera_id, name, url, None)
        except RuntimeError as e:
            warning = str(e)

    logger.info(f"Discovery registered {name} ({redact_url(url)}).")

    return {
        "camera_id": camera_id,
        "name": name,
        "started": started,
        "warning": warning,
    }


def connect_device(request: ConnectRequest) -> dict:
    if request.kind == "webcam":
        name = request.label or f"Webcam {request.port}"
        added = _register(name, f"webcam://{request.port}", "This device")

        return {"status": "ok", "added": [added] if added else []}

    if request.kind == "mjpeg":
        name = request.label or f"Phone {request.host}"
        added = _register(name, f"http://{request.host}:{request.port}/video")

        return {"status": "ok", "added": [added] if added else []}

    result = scanner.resolve_streams(
        request.host,
        request.port,
        request.username,
        request.password,
        settings.discovery_max_channels,
    )

    added = []

    if result["status"] == "ok":
        vendor = result["vendor"]
        many = len(result["streams"]) > 1

        for stream in result["streams"]:
            name = f"{vendor} {request.host}"

            if many:
                name += f" · channel {stream['channel']}"

            registered = _register(name, stream["url"])

            if registered:
                added.append(registered)

    return {
        "status": result["status"],
        "vendor": result["vendor"],
        "streams_found": len(result["streams"]),
        "added": added,
    }


def auto_discover() -> None:
    """
    Boot-time pass. Registers everything that can be connected without asking
    anyone: attached webcams, phone camera apps, and recorders/IP cameras when
    a site-wide login is configured (CAMERA_DEFAULT_USERNAME / _PASSWORD).
    """
    try:
        devices = _annotate(run_scan())
    except Exception as e:
        logger.warning(f"Auto-discovery scan failed: {e}")
        return

    for device in devices:
        if device["already_added"]:
            continue

        needs_login = device["kind"] == "rtsp"

        if needs_login and not settings.camera_default_username:
            logger.info(
                f"Found {device['label']} at {device['host']}:{device['port']} - "
                "waiting for a login from the dashboard."
            )
            continue

        try:
            result = connect_device(
                ConnectRequest(
                    kind=device["kind"],
                    host=device["host"] if device["kind"] != "webcam" else "",
                    port=device["port"],
                    username=settings.camera_default_username if needs_login else "",
                    password=settings.camera_default_password if needs_login else "",
                    label=None if needs_login else device["label"],
                )
            )

            logger.info(
                f"Auto-discovery: {device['label']} -> {result['status']}, "
                f"{len(result['added'])} camera(s) added."
            )
        except Exception as e:
            logger.warning(f"Auto-discovery could not connect {device['host']}: {e}")


def start_auto_discover() -> None:
    if not settings.auto_discover_on_start:
        return

    threading.Thread(target=auto_discover, name="auto-discover", daemon=True).start()


@router.post("/discovery/scan")
def discovery_scan():
    """Scans the local network and attached devices. Takes several seconds."""
    return {"devices": _annotate(run_scan())}


@router.get("/discovery/devices")
def discovery_devices():
    """Result of the most recent scan (the boot-time one, if none since)."""
    return {
        "scanned": _last_scan["scanned"],
        "devices": _annotate(_last_scan["devices"]),
    }


@router.post("/discovery/connect")
def discovery_connect(request: ConnectRequest):
    if request.kind != "webcam" and not request.host:
        raise HTTPException(status_code=422, detail="host is required")

    result = connect_device(request)

    messages = {
        "auth_failed": "The camera rejected that username or password.",
        "no_streams": "Connected, but no channel is delivering video.",
        "unreachable": "The device did not respond.",
    }

    if result["status"] in messages:
        result["message"] = messages[result["status"]]

    return result
