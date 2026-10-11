# app/api/live.py

"""
Live monitoring surface: WebSocket push plus REST history.

The WebSocket carries everything the pipeline produces (detections, event
open/close, alerts, camera state). REST is for anything a client needs to
reconstruct after connecting or reloading, since the socket only ever carries
what happened while it was attached.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Iterable, Iterator, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core.timeutil import iso_utc
from app.db.models import Alert, Camera, Event
from app.db.session import SessionLocal, get_db
from app.services import runtime
from app.streaming.broadcaster import broadcaster
from app.streaming.preview import placeholder, render_preview

logger = logging.getLogger("nexgen.api.live")

router = APIRouter(prefix="/api/v1", tags=["live"])

# Keeps an idle socket alive through proxies that cull quiet connections.
_PING_INTERVAL_SECONDS = 20.0


def _public_url(key: Optional[str]) -> Optional[str]:
    storage = runtime.get_storage()

    return storage.public_url(key) if storage is not None else None


def _event_snapshots(db: Session, alerts: Iterable[Alert]) -> Dict[str, str]:
    """Maps event id -> snapshot key, so alert rows can show a thumbnail."""
    event_ids = {a.event_id for a in alerts if a.event_id}

    if not event_ids:
        return {}

    rows = (
        db.query(Event.id, Event.snapshot_key)
        .filter(Event.id.in_(event_ids))
        .all()
    )

    return {event_id: key for event_id, key in rows if key}


def _serialize_event(event: Event) -> dict:
    return {
        "event_id": event.id,
        "camera_id": event.camera_id,
        "event_type": event.event_type,
        "risk_level": event.risk_level,
        "status": event.status,
        "started_at": iso_utc(event.started_at),
        "ended_at": iso_utc(event.ended_at),
        "detection_count": event.detection_count,
        "summary": event.summary,
        "snapshot_key": event.snapshot_key,
        "clip_key": event.clip_key,
        "snapshot_url": _public_url(event.snapshot_key),
        "clip_url": _public_url(event.clip_key),
    }


def _serialize_alert(alert: Alert, snapshots: Optional[Dict[str, str]] = None) -> dict:
    return {
        "alert_id": alert.id,
        "event_id": alert.event_id,
        "camera_id": alert.camera_id,
        "priority": alert.priority,
        "title": alert.title,
        "message": alert.message,
        "recommended_action": alert.recommended_action,
        "acknowledged": alert.acknowledged,
        "created_at": iso_utc(alert.created_at),
        "snapshot_url": _public_url((snapshots or {}).get(alert.event_id)),
    }


# -----------------------------
# WebSocket
# -----------------------------
@router.websocket("/ws/live")
async def live_feed(
    websocket: WebSocket,
    camera_id: Optional[str] = Query(default=None),
):
    """
    Streams live pipeline messages.

    Message envelope is always `{"type": ..., "camera_id": ...}`; `type` is one
    of: `snapshot`, `detection`, `event.opened`, `event.closed`,
    `event.clip_ready`, `event.analysis`, `alert`, `alert.updated`,
    `camera.status`, `ping`.

    Pass `?camera_id=` to receive only one camera's traffic.
    """
    await websocket.accept()

    subscriber = broadcaster.subscribe(camera_id)

    try:
        # Built off the event loop: it is a blocking database read.
        await websocket.send_json(
            await asyncio.to_thread(_initial_snapshot, camera_id)
        )

        while True:
            try:
                message = await asyncio.wait_for(
                    subscriber.queue.get(),
                    timeout=_PING_INTERVAL_SECONDS,
                )
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                continue

            await websocket.send_json(message)

    except WebSocketDisconnect:
        pass

    except Exception as e:
        logger.info(f"WebSocket closed: {e}")

    finally:
        broadcaster.unsubscribe(subscriber)


def _initial_snapshot(camera_id: Optional[str]) -> dict:
    """
    Current state on connect, so a client renders immediately instead of
    waiting for the next event to arrive.
    """
    manager = runtime.get_stream_manager()

    db = SessionLocal()

    try:
        query = db.query(Camera)

        if camera_id:
            query = query.filter(Camera.id == camera_id)

        cameras = [
            {
                "camera_id": c.id,
                "name": c.name,
                "location": c.location,
                "enabled": c.enabled,
                "status": c.status,
                "running": manager.is_running(c.id) if manager else False,
                "last_error": c.last_error,
            }
            for c in query.all()
        ]

        alert_query = db.query(Alert).order_by(Alert.created_at.desc())

        if camera_id:
            alert_query = alert_query.filter(Alert.camera_id == camera_id)

        alert_rows = alert_query.limit(20).all()
        snapshots = _event_snapshots(db, alert_rows)
        recent_alerts = [_serialize_alert(a, snapshots) for a in alert_rows]

    except Exception as e:
        logger.warning(f"Could not build initial snapshot: {e}")
        cameras = []
        recent_alerts = []

    finally:
        db.close()

    return {
        "type": "snapshot",
        "camera_id": camera_id,
        "cameras": cameras,
        "recent_alerts": recent_alerts,
        "open_tracks": (
            manager.camera_status(camera_id) if manager and camera_id else None
        ),
    }


# -----------------------------
# Event history
# -----------------------------
@router.get("/events")
def list_events(
    camera_id: Optional[str] = None,
    risk_level: Optional[str] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    minutes: Optional[int] = Query(default=None, ge=1, le=10080),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Event)

    if camera_id:
        query = query.filter(Event.camera_id == camera_id)

    if risk_level:
        query = query.filter(Event.risk_level == risk_level)

    if event_type:
        query = query.filter(Event.event_type == event_type)

    if status:
        query = query.filter(Event.status == status)

    if minutes:
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        query = query.filter(Event.started_at >= cutoff)

    total = query.count()

    events = (
        query.order_by(Event.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "count": len(events),
        "offset": offset,
        "events": [_serialize_event(e) for e in events],
    }


@router.get("/events/{event_id}")
def get_event(event_id: str, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    alerts = db.query(Alert).filter(Alert.event_id == event_id).all()

    # snapshot_url / clip_url are resolved on read rather than stored,
    # because OSS signed URLs expire.
    body = _serialize_event(event)
    body["payload"] = event.payload
    body["alerts"] = [_serialize_alert(a) for a in alerts]

    return body


# -----------------------------
# Alerts
# -----------------------------
@router.get("/alerts")
def list_alerts(
    camera_id: Optional[str] = None,
    priority: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    minutes: Optional[int] = Query(default=None, ge=1, le=10080),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Alert)

    if camera_id:
        query = query.filter(Alert.camera_id == camera_id)

    if priority:
        query = query.filter(Alert.priority == priority.upper())

    if acknowledged is not None:
        query = query.filter(Alert.acknowledged.is_(acknowledged))

    if minutes:
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        query = query.filter(Alert.created_at >= cutoff)

    total = query.count()

    alerts = (
        query.order_by(Alert.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "count": len(alerts),
        "offset": offset,
        "alerts": [
            _serialize_alert(a, snapshots)
            for snapshots in [_event_snapshots(db, alerts)]
            for a in alerts
        ],
    }


@router.post("/alerts/{alert_id}/ack")
def acknowledge_alert(alert_id: str, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()

    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.acknowledged = True
    db.commit()

    broadcaster.publish(
        {
            "type": "alert.acknowledged",
            "camera_id": alert.camera_id,
            "alert_id": alert_id,
        }
    )

    return {"alert_id": alert_id, "acknowledged": True}


# -----------------------------
# In-memory detection buffer
# -----------------------------
@router.get("/cameras/{camera_id}/detections")
def recent_detections(
    camera_id: str,
    limit: int = Query(default=50, ge=1, le=500),
):
    """
    Raw per-frame detections from the camera's ring buffer.

    These are not persisted, so the window is bounded by
    LIVE_DETECTION_BUFFER_SIZE and resets when the camera restarts.
    """
    manager = runtime.get_stream_manager()

    if manager is None:
        raise HTTPException(
            status_code=503,
            detail="Stream manager is not initialized.",
        )

    if not manager.is_running(camera_id):
        return {
            "camera_id": camera_id,
            "running": False,
            "detections": [],
            "note": "Camera is not currently streaming.",
        }

    detections = manager.recent_detections(camera_id, limit)

    return {
        "camera_id": camera_id,
        "running": True,
        "count": len(detections),
        "detections": detections,
    }


# -----------------------------
# Browser video + evidence files
# -----------------------------
_MJPEG_BOUNDARY = "frame"


def _require_pipeline(camera_id: str):
    manager = runtime.get_stream_manager()

    if manager is None:
        raise HTTPException(
            status_code=503,
            detail="Stream manager is not initialized.",
        )

    if not manager.has_pipeline(camera_id):
        raise HTTPException(status_code=404, detail="Camera is not running.")

    return manager


@router.get("/cameras/{camera_id}/snapshot.jpg")
def camera_snapshot(
    camera_id: str,
    width: int = Query(default=0, ge=0, le=3840),
    overlay: bool = Query(default=True),
):
    """
    Newest decoded frame as a JPEG. Detections are drawn on unless
    `overlay=false`, which face enrollment uses to get a clean picture.
    """
    manager = _require_pipeline(camera_id)

    latest = manager.latest_frame(camera_id)

    if latest is None:
        raise HTTPException(status_code=503, detail="No frame received yet.")

    _, frame, detections = latest

    data = render_preview(
        frame,
        detections if overlay else None,
        width,
        quality=75 if overlay else 92,
    )

    if data is None:
        raise HTTPException(status_code=500, detail="Could not encode frame.")

    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


def _mjpeg_frames(manager, camera_id: str, fps: float, width: int) -> Iterator[bytes]:
    """
    Always yields within about a second, even when the camera is stalled, by
    repeating the last image. That is what lets the server notice a closed
    browser tab instead of parking a worker thread on a dead stream.
    """
    interval = 1.0 / fps
    last_seq = -1
    last_jpeg = placeholder("Connecting to camera...", width or 640)
    last_sent = 0.0

    while manager.has_pipeline(camera_id):
        latest = manager.latest_frame(camera_id)
        now = time.monotonic()

        if latest is not None and latest[0] != last_seq:
            last_seq, frame, overlay = latest
            last_jpeg = render_preview(frame, overlay, width) or last_jpeg
        elif now - last_sent < 1.0:
            time.sleep(0.05)
            continue

        last_sent = now

        yield (
            f"--{_MJPEG_BOUNDARY}\r\n"
            "Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(last_jpeg)}\r\n\r\n"
        ).encode() + last_jpeg + b"\r\n"

        time.sleep(interval)


@router.get("/cameras/{camera_id}/stream.mjpg")
def camera_stream(
    camera_id: str,
    fps: float = Query(default=10.0, gt=0, le=25),
    width: int = Query(default=960, ge=0, le=3840),
):
    """
    Live preview as MJPEG, playable by a plain <img> tag. Each open stream
    holds one connection, so the dashboard uses it only for the single-camera
    view and polls snapshot.jpg for thumbnails.
    """
    manager = _require_pipeline(camera_id)

    return StreamingResponse(
        _mjpeg_frames(manager, camera_id, fps, width),
        media_type=f"multipart/x-mixed-replace; boundary={_MJPEG_BOUNDARY}",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/artifacts/{artifact_path:path}")
def get_artifact(artifact_path: str):
    """Serves locally stored snapshots, crops and clips to the dashboard."""
    storage = runtime.get_storage()

    path = storage.local_artifact_path(artifact_path) if storage else None

    if path is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return FileResponse(path)
