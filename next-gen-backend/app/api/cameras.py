# app/api/cameras.py

"""
Camera registry.

Cameras are persisted so the service can resume its streams unattended after
a restart, and so events can be attributed to a stable camera id rather than
to a URL that may be re-pointed later.

Mutating a live camera's URL or sample rate restarts its pipeline, since both
values are captured when the capture/analyzer threads are constructed.
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.schemas import CameraCreate, CameraUpdate
from app.db.models import Camera
from app.db.session import get_db
from app.services import runtime

logger = logging.getLogger("nexgen.api.cameras")

router = APIRouter(prefix="/api/v1", tags=["cameras"])


def _serialize(camera: Camera, running: bool) -> dict:
    return {
        "camera_id": camera.id,
        "name": camera.name,
        "rtsp_url": camera.rtsp_url,
        "location": camera.location,
        "enabled": camera.enabled,
        "status": camera.status,
        "running": running,
        "last_error": camera.last_error,
        "last_frame_at": camera.last_frame_at,
        "sample_fps": camera.sample_fps or settings.stream_sample_fps,
        "created_at": camera.created_at,
        "updated_at": camera.updated_at,
    }


def _require_manager():
    manager = runtime.get_stream_manager()

    if manager is None:
        raise HTTPException(
            status_code=503,
            detail="Stream manager is not initialized.",
        )

    return manager


def _get_camera(db: Session, camera_id: str) -> Camera:
    camera = db.query(Camera).filter(Camera.id == camera_id).first()

    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    return camera


@router.get("/cameras")
def list_cameras(db: Session = Depends(get_db)):
    manager = runtime.get_stream_manager()

    cameras = db.query(Camera).order_by(Camera.created_at.asc()).all()

    return {
        "count": len(cameras),
        "running": manager.running_count if manager else 0,
        "max_cameras": settings.max_cameras,
        "cameras": [
            _serialize(c, manager.is_running(c.id) if manager else False)
            for c in cameras
        ],
    }


@router.get("/cameras/status")
def cameras_status():
    """Live pipeline telemetry: connection state, throughput, open tracks."""
    manager = _require_manager()

    return {
        "running": manager.running_count,
        "max_cameras": settings.max_cameras,
        "pipelines": manager.all_status(),
    }


@router.post("/cameras", status_code=201)
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)):
    # Registration is a plain DB write, so it is allowed even if the streaming
    # subsystem is unavailable; only the start attempt below needs a manager.
    manager = runtime.get_stream_manager()

    existing = db.query(Camera).filter(Camera.rtsp_url == payload.rtsp_url).first()

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Stream URL already registered to camera {existing.id}",
        )

    camera = Camera(
        id=f"cam_{uuid4().hex[:12]}",
        name=payload.name,
        rtsp_url=payload.rtsp_url,
        location=payload.location,
        enabled=payload.enabled,
        sample_fps=payload.sample_fps,
        status="offline",
    )

    db.add(camera)
    db.commit()
    db.refresh(camera)

    started = False

    if camera.enabled:
        if manager is None:
            return {
                **_serialize(camera, False),
                "started": False,
                "warning": (
                    "Camera registered, but the stream manager is not "
                    "initialized, so it was not started."
                ),
            }

        try:
            started = manager.start_camera(
                camera.id,
                camera.name,
                camera.rtsp_url,
                camera.sample_fps,
            )
        except RuntimeError as e:
            # The camera is registered but could not be started (usually the
            # camera limit). Surface that instead of silently succeeding.
            return {
                **_serialize(camera, False),
                "started": False,
                "warning": str(e),
            }

    return {**_serialize(camera, started), "started": started}


@router.get("/cameras/{camera_id}")
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    manager = runtime.get_stream_manager()

    camera = _get_camera(db, camera_id)

    body = _serialize(camera, manager.is_running(camera_id) if manager else False)

    if manager is not None:
        body["pipeline"] = manager.camera_status(camera_id)

    return body


@router.patch("/cameras/{camera_id}")
def update_camera(
    camera_id: str,
    payload: CameraUpdate,
    db: Session = Depends(get_db),
):
    manager = _require_manager()

    camera = _get_camera(db, camera_id)

    updates = payload.model_dump(exclude_unset=True)

    # These are read when the threads are built, so they only take effect on
    # a restart of the pipeline.
    restart_required = any(
        field in updates and updates[field] != getattr(camera, field)
        for field in ("rtsp_url", "sample_fps", "name")
    )

    for field, value in updates.items():
        setattr(camera, field, value)

    db.commit()
    db.refresh(camera)

    was_running = manager.is_running(camera_id)

    if not camera.enabled:
        manager.stop_camera(camera_id)

    elif restart_required and was_running:
        try:
            manager.restart_camera(
                camera.id,
                camera.name,
                camera.rtsp_url,
                camera.sample_fps,
            )
        except RuntimeError as e:
            return {
                **_serialize(camera, False),
                "warning": str(e),
            }

    elif camera.enabled and not was_running:
        try:
            manager.start_camera(
                camera.id,
                camera.name,
                camera.rtsp_url,
                camera.sample_fps,
            )
        except RuntimeError as e:
            return {
                **_serialize(camera, False),
                "warning": str(e),
            }

    return _serialize(camera, manager.is_running(camera_id))


@router.delete("/cameras/{camera_id}")
def delete_camera(camera_id: str, db: Session = Depends(get_db)):
    manager = _require_manager()

    camera = _get_camera(db, camera_id)

    manager.stop_camera(camera_id)

    db.delete(camera)
    db.commit()

    # Events and alerts for this camera are deliberately retained: deleting a
    # camera should not erase its incident history.
    return {
        "camera_id": camera_id,
        "deleted": True,
        "note": "Historical events and alerts for this camera were retained.",
    }


@router.post("/cameras/{camera_id}/start")
def start_camera(camera_id: str, db: Session = Depends(get_db)):
    manager = _require_manager()

    camera = _get_camera(db, camera_id)

    if not camera.enabled:
        camera.enabled = True
        db.commit()

    try:
        started = manager.start_camera(
            camera.id,
            camera.name,
            camera.rtsp_url,
            camera.sample_fps,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {
        "camera_id": camera_id,
        "started": started,
        "already_running": not started,
        "status": manager.camera_status(camera_id),
    }


@router.post("/cameras/{camera_id}/stop")
def stop_camera(camera_id: str, db: Session = Depends(get_db)):
    manager = _require_manager()

    camera = _get_camera(db, camera_id)

    # Stopping is treated as operator intent, so the camera is not silently
    # restarted by auto-start on the next boot.
    camera.enabled = False
    db.commit()

    stopped = manager.stop_camera(camera_id)

    return {
        "camera_id": camera_id,
        "stopped": stopped,
        "was_running": stopped,
    }


@router.post("/cameras/{camera_id}/restart")
def restart_camera(camera_id: str, db: Session = Depends(get_db)):
    manager = _require_manager()

    camera = _get_camera(db, camera_id)

    if not camera.enabled:
        camera.enabled = True
        db.commit()

    try:
        manager.restart_camera(
            camera.id,
            camera.name,
            camera.rtsp_url,
            camera.sample_fps,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {
        "camera_id": camera_id,
        "restarted": True,
        "status": manager.camera_status(camera_id),
    }
