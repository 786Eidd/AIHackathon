# app/streaming/tracker.py

"""
Incremental event tracking for live streams.

The batch pipeline could sort every detection in a finished video and merge
neighbours into events. A live stream has no end, so the same grouping has to
happen as an online state machine: each `track key` (an identity name, or a
weapon class) holds an open track that is extended while detections keep
arriving, and closed once it has been quiet for `gap_seconds`.

Tracks are reported twice on purpose:

  * on open  — so an operator is alerted the moment something appears,
               rather than after the subject walks out of frame
  * on close — to finalize duration, detection count and the evidence clip

All timestamps are wall-clock epoch seconds, since there is no video-relative
timeline to reference on a continuous stream.
"""

from __future__ import annotations

import threading
import uuid
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.core.config import settings


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class UnknownFaceClusterer:
    """
    Assigns stable labels to unrecognised faces within one camera.

    Without this, every frame would treat the same stranger as a brand new
    unknown and gap-merging could never group them, producing one event per
    frame. Greedy cosine matching against recent centroids mirrors what the
    batch pipeline did offline, but online and with TTL eviction so labels for
    people who have left do not accumulate forever.
    """

    def __init__(
        self,
        threshold: Optional[float] = None,
        ttl_seconds: Optional[float] = None,
        max_embeddings_per_track: int = 8,
    ):
        self.threshold = (
            threshold
            if threshold is not None
            else settings.unknown_face_cluster_threshold
        )
        self.ttl_seconds = (
            ttl_seconds
            if ttl_seconds is not None
            else settings.unknown_track_ttl_seconds
        )
        self.max_embeddings_per_track = max_embeddings_per_track

        self._tracks: List[dict] = []
        self._counter = 0

    def assign(self, embedding: np.ndarray, timestamp: float) -> str:
        self._evict_expired(timestamp)

        vector = np.asarray(embedding, dtype=np.float32)
        norm = float(np.linalg.norm(vector)) + 1e-10
        vector = vector / norm

        best_track = None
        best_similarity = -1.0

        for track in self._tracks:
            for stored in track["embeddings"]:
                similarity = float(np.dot(vector, stored))

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_track = track

        if best_track is not None and best_similarity >= self.threshold:
            best_track["last_seen"] = timestamp

            if len(best_track["embeddings"]) < self.max_embeddings_per_track:
                best_track["embeddings"].append(vector)

            return best_track["label"]

        self._counter += 1

        label = f"unknown_{self._counter}"

        self._tracks.append(
            {
                "label": label,
                "embeddings": [vector],
                "last_seen": timestamp,
            }
        )

        return label

    def _evict_expired(self, now: float) -> None:
        if self.ttl_seconds <= 0:
            return

        self._tracks = [
            track
            for track in self._tracks
            if now - track["last_seen"] <= self.ttl_seconds
        ]

    @property
    def active_tracks(self) -> int:
        return len(self._tracks)


class LiveEventTracker:
    """
    Per-camera track state. Not shared between cameras, but `observe` and
    `close_stale` may be called from the analyzer thread while `snapshot` is
    read by an API request, so the state is lock-guarded.
    """

    def __init__(self, camera_id: str, gap_seconds: Optional[float] = None):
        self.camera_id = camera_id
        self.gap_seconds = (
            gap_seconds if gap_seconds is not None else settings.event_gap_seconds
        )

        self._lock = threading.Lock()
        self._open_tracks: Dict[str, dict] = {}

    # -----------------------------
    # Observation
    # -----------------------------
    def observe_face(
        self,
        detection: dict,
        timestamp: float,
    ) -> Tuple[Optional[dict], Optional[dict]]:
        """
        Feeds one face detection in.

        Returns (opened_track, closed_track); either may be None. A closed
        track is returned when this detection did not belong to the currently
        open track for the same identity, meaning the previous appearance had
        already ended.
        """
        identity = detection.get("identity_name") or "unknown"
        status = detection.get("status", "unknown")

        key = f"face:{identity}"

        payload = {
            "kind": "face",
            "identity_name": identity,
            "status": status,
            "best_similarity_score": float(detection.get("similarity_score") or 0.0),
            "representative_crop_ref": detection.get("crop_ref"),
            "representative_crop_key": detection.get("crop_key"),
            "bbox": detection.get("bbox"),
        }

        return self._observe(key, payload, timestamp, score_field="best_similarity_score")

    def observe_weapon(
        self,
        detection: dict,
        timestamp: float,
    ) -> Tuple[Optional[dict], Optional[dict]]:
        object_class = detection.get("object_class") or "weapon"

        key = f"weapon:{object_class}"

        payload = {
            "kind": "weapon",
            "object_class": object_class,
            "raw_class": detection.get("raw_class"),
            "max_confidence": float(detection.get("confidence") or 0.0),
            "representative_frame_ref": detection.get("annotated_frame_ref"),
            "representative_frame_key": detection.get("annotated_frame_key"),
            "bbox": detection.get("bbox"),
        }

        return self._observe(key, payload, timestamp, score_field="max_confidence")

    def _observe(
        self,
        key: str,
        payload: dict,
        timestamp: float,
        score_field: str,
    ) -> Tuple[Optional[dict], Optional[dict]]:
        opened = None
        closed = None

        with self._lock:
            existing = self._open_tracks.get(key)

            if existing is not None:
                if timestamp - existing["last_seen"] <= self.gap_seconds:
                    existing["last_seen"] = timestamp
                    existing["detection_count"] += 1

                    # Keep the most confident sighting as the representative
                    # frame, so the evidence attached to the event is the
                    # clearest one rather than merely the first.
                    if payload[score_field] > existing["payload"][score_field]:
                        existing["payload"].update(
                            {k: v for k, v in payload.items() if v is not None}
                        )

                    return None, None

                closed = self._finalize(key, existing)

            track = {
                "track_id": _new_id("track"),
                "key": key,
                "camera_id": self.camera_id,
                "first_seen": timestamp,
                "last_seen": timestamp,
                "detection_count": 1,
                "payload": dict(payload),
                "event_id": None,
            }

            self._open_tracks[key] = track

            opened = self._describe(track)

        return opened, closed

    # -----------------------------
    # Track lifecycle
    # -----------------------------
    def bind_event_id(self, track_id: str, event_id: str) -> None:
        """
        Records the DB event row created for an opened track, so the close
        can update that same row instead of inserting a duplicate.
        """
        with self._lock:
            for track in self._open_tracks.values():
                if track["track_id"] == track_id:
                    track["event_id"] = event_id
                    return

    def close_stale(self, now: float) -> List[dict]:
        """
        Closes tracks that have gone quiet. Must be called regularly by the
        analyzer, otherwise a subject who leaves frame keeps a track open
        until they happen to reappear.
        """
        closed = []

        with self._lock:
            for key in list(self._open_tracks.keys()):
                track = self._open_tracks[key]

                if now - track["last_seen"] > self.gap_seconds:
                    closed.append(self._finalize(key, track))

        return closed

    def close_all(self) -> List[dict]:
        """Flushes every open track, e.g. when a camera is stopped."""
        with self._lock:
            closed = [
                self._finalize(key, track)
                for key, track in list(self._open_tracks.items())
            ]

        return closed

    def _finalize(self, key: str, track: dict) -> dict:
        self._open_tracks.pop(key, None)
        return self._describe(track)

    @staticmethod
    def _describe(track: dict) -> dict:
        return {
            "track_id": track["track_id"],
            "key": track["key"],
            "camera_id": track["camera_id"],
            "first_seen": track["first_seen"],
            "last_seen": track["last_seen"],
            "detection_count": track["detection_count"],
            "event_id": track.get("event_id"),
            **track["payload"],
        }

    def snapshot(self) -> List[dict]:
        with self._lock:
            return [self._describe(track) for track in self._open_tracks.values()]
