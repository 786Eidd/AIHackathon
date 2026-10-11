# app/api/panic.py

"""
Operator panic button.

Pressing it does what an operator would otherwise have to do by hand in the
worst moment: every registered camera is switched on, a picture is taken from
each one that is live, and a HIGH alert goes out to every open dashboard.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.timeutil import iso_utc
from app.db.models import Alert, Camera, Event
from app.db.session import SessionLocal
from app.services import runtime
from app.streaming.broadcaster import broadcaster
from app.streaming.preview import render_preview

logger = logging.getLogger("nexgen.api.panic")

router = APIRouter(prefix="/api/v1", tags=["panic"])

# Used as the camera id of a site-wide alert that no single camera raised.
SITE_CAMERA_ID = "site"


class PanicRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


def _arm_all_cameras() -> int:
    """Enables and starts every registered camera. Returns how many exist."""
    manager = runtime.get_stream_manager()

    db = SessionLocal()

    try:
        cameras = db.query(Camera).all()

        for camera in cameras:
            camera.enabled = True

        db.commit()

        targets = [(c.id, c.name, c.rtsp_url, c.sample_fps) for c in cameras]
    finally:
        db.close()

    if manager is not None:
        for camera_id, name, url, sample_fps in targets:
            try:
                manager.start_camera(camera_id, name, url, sample_fps)
            except RuntimeError as e:
                logger.warning(f"Panic: could not start {camera_id}: {e}")

    return len(targets)


def _capture_evidence(event_id: str) -> list:
    """Saves one frame from each live camera. Returns [(camera_id, key)]."""
    manager = runtime.get_stream_manager()
    storage = runtime.get_storage()

    if manager is None or storage is None:
        return []

    day = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    saved = []

    for status in manager.all_status():
        camera_id = status["camera_id"]
        latest = manager.latest_frame(camera_id)

        if latest is None:
            continue

        data = render_preview(latest[1], None, quality=90)

        if data is None:
            continue

        key = f"artifacts/{camera_id}/{day}/panic/{event_id}.jpg"

        try:
            storage.save_bytes(key, data)
            saved.append((camera_id, key))
        except Exception as e:
            logger.warning(f"Panic: could not save frame for {camera_id}: {e}")

    return saved


@router.post("/panic", status_code=201)
def raise_panic(request: PanicRequest):
    now = datetime.utcnow()
    event_id = f"evt_{uuid4().hex[:12]}"
    alert_id = f"alert_{uuid4().hex[:12]}"

    camera_count = _arm_all_cameras()
    evidence = _capture_evidence(event_id)

    snapshot_key = evidence[0][1] if evidence else None

    summary = (
        f"Panic alarm raised by the operator at "
        f"{now.strftime('%Y-%m-%d %H:%M:%S')} UTC. "
        f"All {camera_count} camera(s) were switched on and "
        f"{len(evidence)} live picture(s) were saved."
    )

    if request.note:
        summary += f"\n\nOperator note: {request.note.strip()}"

    storage = runtime.get_storage()
    snapshot_url = storage.public_url(snapshot_key) if storage else None

    db = SessionLocal()

    try:
        db.add(
            Event(
                id=event_id,
                camera_id=SITE_CAMERA_ID,
                event_type="panic_alarm",
                risk_level="high",
                status="closed",
                started_at=now,
                ended_at=now,
                detection_count=1,
                summary=summary,
                payload={
                    "source": "panic_button",
                    "evidence": [
                        {"camera_id": camera_id, "snapshot_key": key}
                        for camera_id, key in evidence
                    ],
                },
                snapshot_key=snapshot_key,
            )
        )

        db.add(
            Alert(
                id=alert_id,
                event_id=event_id,
                camera_id=SITE_CAMERA_ID,
                priority="HIGH",
                title="panic_alarm",
                message=summary,
                recommended_action="Call the police and follow the site emergency plan.",
                created_at=now,
            )
        )

        db.commit()
    finally:
        db.close()

    alert = {
        "alert_id": alert_id,
        "event_id": event_id,
        "camera_id": SITE_CAMERA_ID,
        "priority": "HIGH",
        "title": "panic_alarm",
        "message": summary,
        "recommended_action": "Call the police and follow the site emergency plan.",
        "acknowledged": False,
        "created_at": iso_utc(now),
        "snapshot_url": snapshot_url,
    }

    broadcaster.publish(
        {
            "type": "event.opened",
            "camera_id": SITE_CAMERA_ID,
            "event": {
                "event_id": event_id,
                "camera_id": SITE_CAMERA_ID,
                "event_type": "panic_alarm",
                "risk_level": "high",
                "status": "closed",
                "started_at": iso_utc(now),
                "summary": summary,
                "snapshot_key": snapshot_key,
                "snapshot_url": snapshot_url,
            },
        }
    )

    broadcaster.publish(
        {"type": "alert", "camera_id": SITE_CAMERA_ID, "alert": alert}
    )

    logger.warning(f"PANIC alarm raised ({alert_id}).")

    return {
        "alert": alert,
        "cameras_armed": camera_count,
        "pictures_saved": len(evidence),
    }
