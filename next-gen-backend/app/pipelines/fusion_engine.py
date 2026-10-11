# app/pipelines/fusion_engine.py

"""
Turns tracked detections into scored security events and operator alerts.

The risk model is the same one the offline pipeline used, but applied one
event at a time: a live stream has no complete detection list to cross-
reference, so weapon/face correlation is done against the tracks that are
currently open on that camera rather than against the whole timeline.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.integrations.qwen import QwenClient
from app.pipelines.prompts import build_alert_prompt
from app.pipelines.weapon_detector import LETHAL_CLASSES


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _format_time(epoch_seconds: Optional[float]) -> str:
    if not epoch_seconds:
        return "unknown time"

    return (
        datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
        .strftime("%Y-%m-%d %H:%M:%S UTC")
    )


def fuse_face_event(
    track: Dict[str, Any],
    open_weapon_tracks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Scores a face track.

    A recognised person is informational. An unrecognised one is medium risk
    on its own, but escalates to high if a weapon is concurrently tracked on
    the same camera — an unknown subject who is also armed is the case that
    must not sit in a low-priority queue.
    """
    identity = track.get("identity_name", "unknown")
    status = track.get("status", "unknown")

    # Only real weapons make an unknown person "armed"; someone near a pair
    # of scissors is not.
    concurrent_weapons = [
        t.get("object_class")
        for t in (open_weapon_tracks or [])
        if t.get("object_class") in LETHAL_CLASSES
    ]

    if status == "known":
        return {
            "event_type": "known_face_detected",
            "risk_level": "info",
            "summary": (
                f"Known person '{identity}' detected at "
                f"{_format_time(track.get('first_seen'))}."
            ),
        }

    if concurrent_weapons:
        return {
            "event_type": "armed_unknown_person",
            "risk_level": "high",
            "summary": (
                f"Unrecognised person ({identity}) detected at "
                f"{_format_time(track.get('first_seen'))} while "
                f"{', '.join(sorted(set(concurrent_weapons)))} "
                "is also being tracked on this camera."
            ),
        }

    summary = (
        f"Unrecognised person ({identity}) detected at "
        f"{_format_time(track.get('first_seen'))}."
    )

    # The score is -1 when nobody is enrolled, which is noise, not evidence.
    best_score = track.get("best_similarity_score") or 0.0

    if best_score > 0:
        summary += f" Closest enrolled match scored {best_score:.2f}."

    return {
        "event_type": "unknown_face_detected",
        "risk_level": "medium",
        "summary": summary,
    }


def fuse_weapon_event(
    track: Dict[str, Any],
    open_face_tracks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Scores a weapon track, attributing it to whoever is currently in frame.
    """
    object_class = track.get("object_class", "weapon")

    known_names = [
        t.get("identity_name")
        for t in (open_face_tracks or [])
        if t.get("status") == "known"
    ]

    unknown_names = [
        t.get("identity_name")
        for t in (open_face_tracks or [])
        if t.get("status") == "unknown"
    ]

    if known_names:
        subject = f"Known person(s): {', '.join(n for n in known_names if n)}"
    elif unknown_names:
        subject = f"Unknown subject(s): {', '.join(n for n in unknown_names if n)}"
    else:
        subject = "No associated face detected"

    lethal = object_class in LETHAL_CLASSES
    readable = object_class.replace("_", " ")

    return {
        "event_type": f"{object_class}_detected",
        # A knife or gun is an emergency. A bat or scissors is usually
        # innocent, so it asks for a look rather than a police call.
        "risk_level": "high" if lethal else "medium",
        "summary": (
            f"{readable.capitalize()} detected at "
            f"{_format_time(track.get('first_seen'))}"
            f"{'' if lethal else ' - this can be used as a weapon'}. "
            f"{subject}. "
            f"Detector confidence: {track.get('max_confidence', 0.0):.2f}."
        ),
    }


def fuse_scene_analysis(
    analysis: Dict[str, Any],
    timestamp: float,
) -> Optional[Dict[str, Any]]:
    """
    Promotes a VLM scene verdict to an event, but only when the model is
    actually claiming elevated risk. Low/medium scene chatter would otherwise
    bury the detector-driven events.
    """
    risk_level = (analysis.get("risk_level") or "low").lower()

    if risk_level != "high":
        return None

    summary = analysis.get("scene_summary") or (
        "Vision analysis flagged a high-risk scene."
    )

    dangerous_objects = analysis.get("dangerous_objects") or []

    if dangerous_objects and isinstance(dangerous_objects, list):
        summary += f" Objects noted: {', '.join(str(o) for o in dangerous_objects)}."

    return {
        "event_type": "suspicious_scene",
        "risk_level": "high",
        "summary": summary,
    }


def fuse_temporal_analysis(
    analysis: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Interprets a multi-frame VLM verdict. Used to enrich an already-open
    event, not to raise a new one, so the caller decides what to do with it.
    """
    event_detected = analysis.get("event_detected", False)
    risk_level = (analysis.get("risk_level") or "low").lower()

    if not event_detected and risk_level not in ("medium", "high"):
        return None

    event_type = analysis.get("event_type") or "temporal_security_event"

    event_type = str(event_type).lower().replace(" ", "_").replace("/", "_")

    explanation = analysis.get("explanation") or (
        "Temporal vision analysis detected a possible security event."
    )

    confidence = analysis.get("confidence")

    summary = explanation

    if confidence is not None:
        summary += f" Model confidence: {confidence}."

    return {
        "event_type": event_type,
        "risk_level": risk_level if risk_level in ("medium", "high") else "medium",
        "summary": summary,
    }


PRIORITY_MAP = {
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "info": "INFO",
}


def template_alert_message(event: Dict[str, Any]) -> str:
    priority = (event.get("risk_level") or "low").upper()

    return (
        f"{priority} ALERT\n\n"
        f"{event.get('summary', 'Security event detected.')}\n\n"
        "Recommended action: review the associated footage and verify the scene."
    )


def should_alert(risk_level: str) -> bool:
    """Informational events are recorded but never paged out."""
    return (risk_level or "low").lower() not in ("info", "low")


def build_alert(
    event: Dict[str, Any],
    message: Optional[str] = None,
) -> Dict[str, Any]:
    risk_level = (event.get("risk_level") or "low").lower()

    return {
        "alert_id": _new_id("alert"),
        "event_id": event.get("event_id"),
        "camera_id": event.get("camera_id"),
        "priority": PRIORITY_MAP.get(risk_level, "LOW"),
        "title": event.get("event_type", "security_event"),
        "message": (message or template_alert_message(event)).strip(),
        "recommended_action": (
            "Security operator should review the footage and verify the scene."
        ),
    }


def enrich_alert_message(
    event: Dict[str, Any],
    qwen_client: Optional[QwenClient] = None,
) -> Optional[str]:
    """
    Asks the text model for a better-worded alert.

    Called from the background Qwen executor, never inline with detection —
    a weapon alert must not wait on a cloud round trip.
    """
    if qwen_client is None or not qwen_client.enabled:
        return None

    try:
        prompt = build_alert_prompt(event)
        message = qwen_client.generate_text(prompt)
    except Exception:
        return None

    if not message or not message.strip():
        return None

    return message.strip()
