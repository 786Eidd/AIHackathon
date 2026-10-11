# app/api/endpoints.py

"""
Service health, identity management and operator chat.

Chat is scoped to a camera and a lookback window rather than to a recording,
since on a live system the question an operator asks is "what happened on the
lobby camera in the last hour", not "what is in this file".
"""

import base64
import binascii
import io
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.schemas import ChatRequest, IdentityEnroll
from app.core.timeutil import iso_utc
from app.db.models import Alert, Camera, Event
from app.db.session import get_db
from app.services import runtime

logger = logging.getLogger("nexgen.api")

router = APIRouter(prefix="/api/v1", tags=["core"])

# Bounds the context handed to the text model; a busy camera can accumulate
# far more history than fits in a prompt.
_MAX_CONTEXT_CHARS = 20000
_MAX_CONTEXT_EVENTS = 60
_MAX_CONTEXT_ALERTS = 30


@router.get("/health")
def health():
    face_embedder = runtime.get_face_embedder()
    identity_store = runtime.get_identity_store()
    weapon_detector = runtime.get_weapon_detector()
    qwen_client = runtime.get_qwen_client()
    manager = runtime.get_stream_manager()

    return {
        "status": "ok",
        "device": settings.computed_device,
        "face_module_loaded": face_embedder is not None,
        "identity_store_loaded": identity_store is not None,
        "identity_count": (
            len(identity_store.list_identities())
            if identity_store is not None
            else 0
        ),
        "weapon_model_loaded": (
            weapon_detector.loaded if weapon_detector is not None else False
        ),
        "qwen_enabled": qwen_client.enabled if qwen_client is not None else False,
        "streaming": {
            "manager_ready": manager is not None,
            "cameras_running": manager.running_count if manager else 0,
            "max_cameras": settings.max_cameras,
            "sample_fps": settings.stream_sample_fps,
            "inference_width": settings.stream_inference_width,
            "websocket_subscribers": _subscriber_count(),
        },
    }


def _subscriber_count() -> int:
    from app.streaming.broadcaster import broadcaster

    return broadcaster.subscriber_count


@router.get("/identities")
def list_identities():
    identity_store = runtime.get_identity_store()

    if identity_store is None:
        return {
            "identities": [],
            "message": "Identity store not loaded",
        }

    return {"identities": identity_store.list_identities()}


@router.post("/identities/reload")
def reload_identities():
    """
    Picks up a re-enrolled identity store without restarting the service.
    Running cameras switch to the new store on their next match.
    """
    identity_store = runtime.reload_identity_store()

    return {
        "status": "reloaded",
        "identity_count": len(identity_store.list_identities()),
        "identities": identity_store.list_identities(),
    }


# Decoded size cap per enrollment photo.
_MAX_ENROLL_IMAGE_BYTES = 10 * 1024 * 1024


def _decode_image(value: str):
    from PIL import Image

    if value.startswith("data:") and "," in value:
        value = value.split(",", 1)[1]

    try:
        raw = base64.b64decode(value, validate=False)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="Image is not valid base64.")

    if len(raw) > _MAX_ENROLL_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image is larger than 10 MB.")

    try:
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read image.")


@router.post("/identities", status_code=201)
def enroll_identity(payload: IdentityEnroll):
    """
    Enrolls a person from one or more photos. Enrolling an existing name adds
    the new photos to it. Takes effect on running cameras immediately.
    """
    inference = runtime.get_inference()

    if inference is None or not inference.face_available:
        raise HTTPException(status_code=503, detail="Face module is not loaded.")

    images = [_decode_image(value) for value in payload.images]

    try:
        report = inference.enroll_identity(payload.name, images)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    runtime.persist_identity_store()

    return {
        **report,
        "identities": runtime.get_identity_store().list_identities(),
    }


@router.delete("/identities/{name}")
def delete_identity(name: str):
    inference = runtime.get_inference()

    if inference is None or not inference.remove_identity(name):
        raise HTTPException(status_code=404, detail="Identity not found")

    runtime.persist_identity_store()

    return {
        "name": name,
        "deleted": True,
        "identities": runtime.get_identity_store().list_identities(),
    }


@router.post("/chat")
def operator_chat(request: ChatRequest, db: Session = Depends(get_db)):
    qwen_client = runtime.get_qwen_client()

    if qwen_client is None or not qwen_client.enabled:
        return {
            "camera_id": request.camera_id,
            "answer": "Qwen chat is not configured. Please set DASHSCOPE_API_KEY.",
        }

    if request.camera_id:
        camera = (
            db.query(Camera).filter(Camera.id == request.camera_id).first()
        )

        if camera is None:
            raise HTTPException(status_code=404, detail="Camera not found")

    cutoff = datetime.utcnow() - timedelta(minutes=request.minutes)

    context = _build_chat_context(db, request.camera_id, cutoff)

    if not context["events"] and not context["alerts"]:
        return {
            "camera_id": request.camera_id,
            "question": request.question,
            "answer": (
                f"No security events were recorded in the last "
                f"{request.minutes} minute(s) for this scope."
            ),
        }

    from app.pipelines.prompts import build_chat_prompt

    prompt = build_chat_prompt(request.question, context)
    answer = qwen_client.generate_text(prompt)

    if not answer:
        answer = "Sorry, I could not generate an answer right now."

    return {
        "camera_id": request.camera_id,
        "question": request.question,
        "window_minutes": request.minutes,
        "events_considered": len(context["events"]),
        "answer": answer.strip(),
    }


def _build_chat_context(
    db: Session,
    camera_id: Optional[str],
    cutoff: datetime,
) -> dict:
    event_query = db.query(Event).filter(Event.started_at >= cutoff)
    alert_query = db.query(Alert).filter(Alert.created_at >= cutoff)

    if camera_id:
        event_query = event_query.filter(Event.camera_id == camera_id)
        alert_query = alert_query.filter(Alert.camera_id == camera_id)

    events = (
        event_query.order_by(Event.started_at.desc())
        .limit(_MAX_CONTEXT_EVENTS)
        .all()
    )

    alerts = (
        alert_query.order_by(Alert.created_at.desc())
        .limit(_MAX_CONTEXT_ALERTS)
        .all()
    )

    context = {
        "camera_id": camera_id,
        "window_start": iso_utc(cutoff),
        "summary": _summarize(events, alerts),
        "events": [
            {
                "event_id": e.id,
                "camera_id": e.camera_id,
                "event_type": e.event_type,
                "risk_level": e.risk_level,
                "started_at": iso_utc(e.started_at),
                "ended_at": iso_utc(e.ended_at),
                "detection_count": e.detection_count,
                "summary": e.summary,
            }
            for e in events
        ],
        "alerts": [
            {
                "alert_id": a.id,
                "camera_id": a.camera_id,
                "priority": a.priority,
                "title": a.title,
                "message": a.message,
                "acknowledged": a.acknowledged,
            }
            for a in alerts
        ],
    }

    # Trim oldest events until the serialized context fits the prompt budget.
    while (
        len(json.dumps(context, ensure_ascii=False, default=str))
        > _MAX_CONTEXT_CHARS
        and context["events"]
    ):
        context["events"].pop()

    return context


def _summarize(events, alerts) -> dict:
    return {
        "total_events": len(events),
        "high_risk_events": len([e for e in events if e.risk_level == "high"]),
        "medium_risk_events": len([e for e in events if e.risk_level == "medium"]),
        "known_face_events": len(
            [e for e in events if e.event_type == "known_face_detected"]
        ),
        "unknown_face_events": len(
            [e for e in events if e.event_type == "unknown_face_detected"]
        ),
        "weapon_events": len(
            [e for e in events if e.event_type == "armed_unknown_person"
             or (e.event_type.endswith("_detected")
                 and e.event_type not in (
                     "known_face_detected",
                     "unknown_face_detected",
                 ))]
        ),
        "total_alerts": len(alerts),
        "unacknowledged_alerts": len([a for a in alerts if not a.acknowledged]),
    }
