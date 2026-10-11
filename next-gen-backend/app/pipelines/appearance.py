# app/pipelines/appearance.py

"""
Plain-language description of an unrecognised person.

Deliberately limited to what a guard could say over a radio and what can be
measured from the picture: the colour of the clothing below the face, and
how often this person has been here before. It does not guess age, gender,
ethnicity or mood — those guesses are unreliable from CCTV and would put
invented facts into a security record.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np

# Below this many pixels the torso patch is too small to judge a colour.
_MIN_PATCH_PIXELS = 400

# A colour must cover this share of the patch to be named on its own.
_DOMINANT_SHARE = 0.38


def clothing_colour(frame: np.ndarray, face_box) -> Optional[str]:
    """
    Names the main colour of the upper clothing, sampled from the area just
    below the face. Returns None when that area is out of frame.
    """
    import cv2

    try:
        x1, y1, x2, y2 = [float(v) for v in face_box]
    except Exception:
        return None

    face_width = x2 - x1
    face_height = y2 - y1

    if face_width <= 0 or face_height <= 0:
        return None

    frame_height, frame_width = frame.shape[:2]

    # Chest: slightly wider than the face, starting below the neck.
    left = int(max(0, x1 - 0.35 * face_width))
    right = int(min(frame_width, x2 + 0.35 * face_width))
    top = int(min(frame_height, y2 + 0.7 * face_height))
    bottom = int(min(frame_height, y2 + 2.2 * face_height))

    if (right - left) * (bottom - top) < _MIN_PATCH_PIXELS:
        return None

    hsv = cv2.cvtColor(frame[top:bottom, left:right], cv2.COLOR_BGR2HSV)

    hue = hsv[..., 0].astype(np.int32).ravel()
    saturation = hsv[..., 1].astype(np.int32).ravel()
    value = hsv[..., 2].astype(np.int32).ravel()

    labels = np.full(hue.shape, "", dtype=object)

    black = value < 55
    white = (saturation < 45) & (value > 190)
    grey = (saturation < 45) & ~black & ~white
    coloured = ~(black | white | grey)

    labels[black] = "black"
    labels[white] = "white"
    labels[grey] = "grey"

    # OpenCV hue runs 0-179.
    for name, low, high in (
        ("red", 0, 8),
        ("orange", 8, 20),
        ("yellow", 20, 33),
        ("green", 33, 85),
        ("teal", 85, 100),
        ("blue", 100, 130),
        ("purple", 130, 150),
        ("pink", 150, 170),
        ("red", 170, 180),
    ):
        labels[coloured & (hue >= low) & (hue < high)] = name

    # Dark, weakly saturated orange reads as brown to a person.
    brown = coloured & (hue >= 8) & (hue < 20) & (value < 140)
    labels[brown] = "brown"

    names, counts = np.unique(labels, return_counts=True)
    order = np.argsort(counts)[::-1]

    top_name = str(names[order[0]])
    top_share = counts[order[0]] / float(labels.size)

    if top_share < _DOMINANT_SHARE:
        return "patterned or multi-coloured"

    if top_name in ("black", "white", "grey", "brown"):
        return top_name

    mask = labels == top_name
    brightness = float(np.median(value[mask]))
    vividness = float(np.median(saturation[mask]))

    if brightness < 110:
        return f"dark {top_name}"

    # Pale means washed out, not merely well lit.
    if brightness > 170 and vividness < 110:
        return f"light {top_name}"

    return top_name


def describe_unknown(
    label: str,
    visits: int,
    first_seen: Optional[float],
    colour: Optional[str],
) -> str:
    """One or two sentences for the alert, e.g. for reading out to a guard."""
    parts = []

    if colour:
        parts.append(f"Appears to be wearing a {colour} top.")

    if visits <= 1:
        parts.append(f"First time {label} has been seen at this site.")
    elif first_seen:
        since = datetime.fromtimestamp(first_seen).strftime("%d %b, %H:%M")
        parts.append(
            f"{label} has been here before: visit {visits}, first seen {since}."
        )

    return " ".join(parts)
