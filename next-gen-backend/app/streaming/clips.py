# app/streaming/clips.py

"""
Event evidence clips.

A live pipeline only learns an event is interesting *after* the triggering
frame, so the seconds leading up to it are already gone unless they were
retained. Each camera therefore keeps a rolling deque of recent sampled
frames; when an event fires, that pre-roll is handed to a recorder which
keeps appending new frames until the post-roll window elapses, then encodes
and uploads on a background thread.

Encoding never happens on the analyzer thread — a 10 second clip write would
otherwise stall detection on that camera.
"""

from __future__ import annotations

import logging
import tempfile
import threading
from collections import deque
from pathlib import Path
from typing import Callable, Deque, List, Optional, Tuple

import numpy as np

from app.core.config import settings

logger = logging.getLogger("nexgen.streaming.clips")

# Guards against a pathological pre-roll setting eating memory: at 1080p a
# frame is ~6MB, so this caps one camera's buffer at roughly 750MB worst case.
_MAX_BUFFERED_FRAMES = 120


class FrameRingBuffer:
    """Rolling pre-event frame history for one camera."""

    def __init__(self, seconds: float, sample_fps: float):
        capacity = int(max(1.0, seconds) * max(0.1, sample_fps))
        capacity = max(1, min(capacity, _MAX_BUFFERED_FRAMES))

        self._frames: Deque[Tuple[float, np.ndarray]] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def add(self, timestamp: float, frame: np.ndarray) -> None:
        # Copied because the capture layer hands out its live slot by
        # reference and will overwrite it on the next decoded frame.
        with self._lock:
            self._frames.append((timestamp, frame.copy()))

    def snapshot(self) -> List[Tuple[float, np.ndarray]]:
        with self._lock:
            return list(self._frames)

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()


class ClipRecorder:
    """
    Collects frames for a single event clip and finalizes itself once the
    post-roll window has passed.
    """

    def __init__(
        self,
        event_id: str,
        camera_id: str,
        storage_key: str,
        pre_roll: List[Tuple[float, np.ndarray]],
        started_at: float,
        post_seconds: float,
        playback_fps: float,
        storage,
        on_complete: Optional[Callable[[str, str], None]] = None,
    ):
        self.event_id = event_id
        self.camera_id = camera_id
        self.storage_key = storage_key
        self.started_at = started_at
        self.post_seconds = post_seconds
        self.playback_fps = max(1.0, playback_fps)

        self._storage = storage
        self._on_complete = on_complete

        self._frames: List[np.ndarray] = [frame for _, frame in pre_roll]
        self._finalized = False

    @property
    def finalized(self) -> bool:
        return self._finalized

    def add_frame(self, timestamp: float, frame: np.ndarray) -> bool:
        """
        Returns True while the recorder still wants frames.
        """
        if self._finalized:
            return False

        if len(self._frames) >= _MAX_BUFFERED_FRAMES * 2:
            self.finalize()
            return False

        self._frames.append(frame.copy())

        if timestamp - self.started_at >= self.post_seconds:
            self.finalize()
            return False

        return True

    def finalize(self) -> None:
        if self._finalized:
            return

        self._finalized = True

        frames = self._frames
        self._frames = []

        if not frames:
            return

        thread = threading.Thread(
            target=self._encode_and_upload,
            args=(frames,),
            name=f"clip-{self.event_id}",
            daemon=True,
        )
        thread.start()

    def _encode_and_upload(self, frames: List[np.ndarray]) -> None:
        import cv2

        temp_path: Optional[Path] = None

        try:
            height, width = frames[0].shape[:2]

            # VideoWriter needs a real filesystem path, so encode to temp and
            # hand the finished file to the storage client (which may be OSS).
            with tempfile.NamedTemporaryFile(
                suffix=".mp4",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)

            writer = cv2.VideoWriter(
                str(temp_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                self.playback_fps,
                (width, height),
            )

            if not writer.isOpened():
                logger.warning(
                    f"[{self.camera_id}] Could not open clip writer for "
                    f"{self.event_id}."
                )
                return

            try:
                for frame in frames:
                    # A camera that changes resolution mid-stream would
                    # otherwise silently produce a corrupt file.
                    if frame.shape[:2] != (height, width):
                        frame = cv2.resize(frame, (width, height))

                    writer.write(frame)
            finally:
                writer.release()

            self._storage.save_file(self.storage_key, temp_path)

            logger.info(
                f"[{self.camera_id}] Clip saved for event {self.event_id}: "
                f"{self.storage_key} ({len(frames)} frames)"
            )

            if self._on_complete is not None:
                self._on_complete(self.event_id, self.storage_key)

        except Exception as e:
            logger.warning(
                f"[{self.camera_id}] Clip encoding failed for "
                f"{self.event_id}: {e}"
            )

        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    pass


def clip_playback_fps(sample_fps: float) -> float:
    """
    Clips are written at the rate frames were actually sampled, so playback
    duration matches real elapsed time instead of appearing sped up.
    """
    return max(1.0, min(30.0, sample_fps))


def clips_enabled() -> bool:
    return bool(settings.enable_event_clips)
