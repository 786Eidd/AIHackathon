# app/streaming/preview.py

"""
Browser preview frames.

The dashboard cannot play RTSP, so the newest decoded frame of each camera is
re-served as JPEG (single snapshot or MJPEG). Detections from the most recent
analysis pass are drawn on top, which is what makes the live view show boxes
without the browser doing any geometry of its own.
"""

from __future__ import annotations

import time
from typing import Optional, Tuple

import numpy as np

# Boxes older than this are not drawn; the subject has probably moved.
_OVERLAY_MAX_AGE_SECONDS = 2.0

_KNOWN = (98, 158, 60)
_UNKNOWN = (32, 160, 224)
_WEAPON = (63, 63, 218)


def render_preview(
    frame: np.ndarray,
    overlay: Optional[Tuple[float, list, list]],
    width: int = 0,
    quality: int = 75,
) -> Optional[bytes]:
    import cv2

    height, native_width = frame.shape[:2]
    scale = 1.0

    if 0 < width < native_width:
        scale = width / float(native_width)
        image = cv2.resize(
            frame,
            (width, max(1, int(round(height * scale)))),
            interpolation=cv2.INTER_AREA,
        )
    else:
        image = frame.copy()

    if overlay is not None and time.time() - overlay[0] <= _OVERLAY_MAX_AGE_SECONDS:
        _, faces, weapons = overlay

        for face in faces:
            known = face.get("status") == "known"
            _draw(
                image,
                face.get("bbox"),
                face.get("identity_name") or "unknown",
                _KNOWN if known else _UNKNOWN,
                scale,
            )

        for weapon in weapons:
            label = f"{weapon.get('object_class', 'weapon')} {weapon.get('confidence', 0):.2f}"
            _draw(image, weapon.get("bbox"), label, _WEAPON, scale)

    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])

    return buffer.tobytes() if ok else None


def placeholder(text: str, width: int = 640) -> bytes:
    import cv2

    height = int(width * 9 / 16)
    image = np.full((height, width, 3), (74, 54, 2), dtype=np.uint8)

    (text_width, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)

    cv2.putText(
        image,
        text,
        (max(8, (width - text_width) // 2), height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (200, 200, 200),
        1,
        cv2.LINE_AA,
    )

    return cv2.imencode(".jpg", image)[1].tobytes()


def _draw(image, bbox, label: str, color, scale: float) -> None:
    import cv2

    try:
        x1, y1, x2, y2 = [int(float(v) * scale) for v in bbox]
    except Exception:
        return

    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

    (text_width, text_height), _ = cv2.getTextSize(
        label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
    )

    top = max(text_height + 6, y1)

    cv2.rectangle(
        image, (x1, top - text_height - 6), (x1 + text_width + 6, top), color, -1
    )
    cv2.putText(
        image,
        label,
        (x1 + 3, top - 4),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
