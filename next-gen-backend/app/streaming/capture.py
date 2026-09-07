# app/streaming/capture.py

"""
RTSP frame capture with a latest-frame-wins buffer.

The core problem with pulling an RTSP stream for analytics is that the
decoder produces frames faster than the models can consume them. If you
simply call `read()` at your inference rate, the frames you get are whatever
was queued *earliest* in the socket buffer, so displayed/analysed footage
drifts further behind real time the longer the service runs — and on a
surveillance system, an alert about something that happened four minutes ago
is close to worthless.

So the reader thread here consumes the stream as fast as the decoder yields,
and keeps only the newest frame in a single mutex-protected slot. Frames the
analyzer never asks for are discarded. That trades completeness (which live
surveillance does not need) for bounded latency (which it does).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Callable, Optional, Tuple

import numpy as np

from app.core.config import settings

logger = logging.getLogger("nexgen.streaming.capture")


class CaptureStatus:
    OFFLINE = "offline"
    CONNECTING = "connecting"
    ONLINE = "online"
    ERROR = "error"


def _build_ffmpeg_options() -> str:
    """
    OpenCV passes this env var through to FFmpeg's AVDictionary when opening
    a capture. It is read at `VideoCapture` construction time, so it has to
    be in the environment before the camera is opened, not merely before
    cv2 is imported.

    `stimeout` is in microseconds and is what stops a dead camera from
    hanging the reader thread forever.
    """
    timeout_us = int(max(1.0, settings.stream_socket_timeout_seconds) * 1_000_000)

    transport = (settings.stream_rtsp_transport or "tcp").strip().lower()

    if transport not in ("tcp", "udp"):
        transport = "tcp"

    return "|".join(
        [
            f"rtsp_transport;{transport}",
            f"stimeout;{timeout_us}",
            "max_delay;500000",
            "reorder_queue_size;0",
        ]
    )


class CameraCapture:
    """
    Owns one reader thread for one camera.

    `read_latest()` is non-blocking and returns the most recent decoded
    frame, or None if nothing has arrived yet. The returned sequence number
    lets a consumer detect that it has already seen this frame and skip
    redundant inference on a stalled stream.
    """

    def __init__(
        self,
        camera_id: str,
        stream_url: str,
        *,
        on_status_change: Optional[Callable[[str, Optional[str]], None]] = None,
    ):
        self.camera_id = camera_id
        self.stream_url = stream_url

        self._on_status_change = on_status_change

        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_monotonic: float = 0.0
        self._latest_wall_clock: float = 0.0
        self._frame_seq: int = 0

        # True while the slot holds a frame no consumer has taken yet, so
        # overwrites can be counted as genuine drops.
        self._frame_pending: bool = False

        self._status = CaptureStatus.OFFLINE
        self._last_error: Optional[str] = None

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._frames_received = 0
        self._frames_dropped = 0
        self._reconnect_count = 0
        self._source_fps: float = 0.0

    # -----------------------------
    # Lifecycle
    # -----------------------------
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run,
            name=f"capture-{self.camera_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop_event.set()

        thread = self._thread

        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)

        self._thread = None
        self._set_status(CaptureStatus.OFFLINE, None)

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def status(self) -> str:
        return self._status

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    # -----------------------------
    # Frame access
    # -----------------------------
    def read_latest(self) -> Optional[Tuple[int, float, np.ndarray]]:
        """
        Returns (frame_seq, wall_clock_timestamp, frame) or None.

        The frame is handed out by reference and must not be mutated by the
        caller; every consumer here either only reads it or calls .copy()
        before drawing on it.
        """
        with self._lock:
            if self._latest_frame is None:
                return None

            self._frame_pending = False

            return (
                self._frame_seq,
                self._latest_wall_clock,
                self._latest_frame,
            )

    def stats(self) -> dict:
        with self._lock:
            last_frame_age = (
                time.monotonic() - self._latest_monotonic
                if self._latest_monotonic
                else None
            )

            return {
                "status": self._status,
                "last_error": self._last_error,
                "frames_received": self._frames_received,
                "frames_dropped": self._frames_dropped,
                "reconnect_count": self._reconnect_count,
                "source_fps": round(self._source_fps, 2),
                "last_frame_age_seconds": (
                    round(last_frame_age, 2) if last_frame_age is not None else None
                ),
            }

    # -----------------------------
    # Internals
    # -----------------------------
    def _set_status(self, status: str, error: Optional[str]) -> None:
        changed = status != self._status or error != self._last_error

        self._status = status
        self._last_error = error

        if changed and self._on_status_change is not None:
            try:
                self._on_status_change(status, error)
            except Exception as e:
                logger.warning(
                    f"Status callback failed for camera {self.camera_id}: {e}"
                )

    def _open(self):
        # Imported lazily and configured immediately before opening, since
        # OpenCV reads the FFmpeg options from the environment at this point.
        import cv2

        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = _build_ffmpeg_options()

        capture = cv2.VideoCapture(self.stream_url, cv2.CAP_FFMPEG)

        if not capture.isOpened():
            capture.release()
            return None

        # Ask the decoder to keep the shallowest queue it will accept. Not
        # every backend honours this, which is exactly why the reader thread
        # below also drains continuously rather than relying on it.
        try:
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        try:
            reported_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)

            # Network cameras routinely report nonsense here.
            if 0.0 < reported_fps <= 240.0:
                self._source_fps = reported_fps
        except Exception:
            pass

        return capture

    def _run(self) -> None:
        backoff = max(0.5, settings.stream_reconnect_initial_seconds)
        max_backoff = max(backoff, settings.stream_reconnect_max_seconds)

        while not self._stop_event.is_set():
            self._set_status(CaptureStatus.CONNECTING, None)

            capture = None

            try:
                capture = self._open()
            except Exception as e:
                logger.warning(f"[{self.camera_id}] Open raised: {e}")
                capture = None

            if capture is None:
                self._reconnect_count += 1

                self._set_status(
                    CaptureStatus.ERROR,
                    f"Could not open stream: {self.stream_url}",
                )

                logger.warning(
                    f"[{self.camera_id}] Connection failed. "
                    f"Retrying in {backoff:.1f}s."
                )

                if self._stop_event.wait(backoff):
                    break

                backoff = min(max_backoff, backoff * 2)
                continue

            logger.info(f"[{self.camera_id}] Stream connected.")

            self._set_status(CaptureStatus.ONLINE, None)

            # Successful connection resets the backoff, so a camera that
            # flaps does not end up stuck at the maximum delay.
            backoff = max(0.5, settings.stream_reconnect_initial_seconds)

            disconnect_reason = self._read_loop(capture)

            try:
                capture.release()
            except Exception:
                pass

            if self._stop_event.is_set():
                break

            self._reconnect_count += 1

            self._set_status(CaptureStatus.ERROR, disconnect_reason)

            logger.warning(
                f"[{self.camera_id}] {disconnect_reason} "
                f"Reconnecting in {backoff:.1f}s."
            )

            if self._stop_event.wait(backoff):
                break

            backoff = min(max_backoff, backoff * 2)

        self._set_status(CaptureStatus.OFFLINE, None)
        logger.info(f"[{self.camera_id}] Capture thread stopped.")

    def _read_loop(self, capture) -> str:
        """
        Drains the stream until it fails. Returns a human-readable reason.
        """
        stall_limit = max(1.0, settings.stream_read_stall_seconds)

        consecutive_failures = 0
        last_success = time.monotonic()

        # Measured over a sliding window rather than trusting CAP_PROP_FPS.
        fps_window_start = time.monotonic()
        fps_window_frames = 0

        while not self._stop_event.is_set():
            try:
                ok, frame = capture.read()
            except Exception as e:
                return f"Read raised: {e}."

            now = time.monotonic()

            if not ok or frame is None:
                consecutive_failures += 1

                # A few dropped reads are normal on a busy network; a
                # sustained gap means the stream is genuinely gone.
                if now - last_success > stall_limit:
                    return (
                        f"No frames for {stall_limit:.0f}s "
                        f"({consecutive_failures} failed reads)."
                    )

                time.sleep(0.05)
                continue

            consecutive_failures = 0
            last_success = now

            with self._lock:
                # A frame still pending in the slot was never consumed by the
                # analyzer, so overwriting it is a real dropped frame.
                if self._frame_pending:
                    self._frames_dropped += 1

                self._latest_frame = frame
                self._latest_monotonic = now
                self._latest_wall_clock = time.time()
                self._frame_seq += 1
                self._frames_received += 1
                self._frame_pending = True

            fps_window_frames += 1
            window_elapsed = now - fps_window_start

            if window_elapsed >= 5.0:
                self._source_fps = fps_window_frames / window_elapsed
                fps_window_start = now
                fps_window_frames = 0

        return "Stopped."
