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
from datetime import datetime, timedelta
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.orm import Session

from app.db.models import Alert, Camera, Event
from app.db.session import SessionLocal, get_db
from app.services import runtime
from app.streaming.broadcaster import broadcaster

logger = logging.getLogger("nexgen.api.live")

router = APIRouter(prefix="/api/v1", tags=["live"])

# Keeps an idle socket alive through proxies that cull quiet connections.
_PING_INTERVAL_SECONDS = 20.0


def _serialize_event(event: Event) -> dict:
    return {
        "event_id": event.id,
        "camera_id": event.camera_id,
        "event_type": event.event_type,
        "risk_level": event.risk_level,
        "status": event.status,
        "started_at": event.started_at.isoformat() if event.started_at else None,
        "ended_at": event.ended_at.isoformat() if event.ended_at else None,
        "detection_count": event.detection_count,
        "summary": event.summary,
        "snapshot_key": event.snapshot_key,
        "clip_key": event.clip_key,
    }


def _serialize_alert(alert: Alert) -> dict:
    return {
        "alert_id": alert.id,
        "event_id": alert.event_id,
        "camera_id": alert.camera_id,
        "priority": alert.priority,
        "title": alert.title,
        "message": alert.message,
        "recommended_action": alert.recommended_action,
        "acknowledged": alert.acknowledged,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
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
        await websocket.send_json(_initial_snapshot(camera_id))

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

        recent_alerts = [_serialize_alert(a) for a in alert_query.limit(20).all()]

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

    storage = runtime.get_storage()

    body = _serialize_event(event)
    body["payload"] = event.payload
    body["alerts"] = [_serialize_alert(a) for a in alerts]

    # Resolved on read rather than stored, because OSS signed URLs expire.
    if storage is not None:
        body["snapshot_url"] = (
            storage.access_reference(event.snapshot_key)
            if event.snapshot_key
            else None
        )
        body["clip_url"] = (
            storage.access_reference(event.clip_key) if event.clip_key else None
        )

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
        "alerts": [_serialize_alert(a) for a in alerts],
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
