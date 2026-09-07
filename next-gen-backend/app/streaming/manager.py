# app/streaming/manager.py

"""
Owns the lifetime of every live camera pipeline.

Each running camera is a pair of threads — capture and analyzer — tracked
together in one `StreamPipeline` record. The manager is the only thing that
creates or destroys those pairs, so start/stop is serialized under a single
lock and a camera can never end up with two analyzers writing events for it.

Capture status changes are mirrored onto the Camera row and pushed to
WebSocket clients, which is how the UI shows a camera going offline.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional

from app.core.config import settings
from app.db.models import Camera
from app.db.session import SessionLocal
from app.streaming.analyzer import CameraAnalyzer
from app.streaming.broadcaster import broadcaster
from app.streaming.capture import CameraCapture
from app.streaming.inference import InferenceService

logger = logging.getLogger("nexgen.streaming.manager")


class StreamPipeline:
    def __init__(self, capture: CameraCapture, analyzer: CameraAnalyzer):
        self.capture = capture
        self.analyzer = analyzer


class StreamManager:
    def __init__(
        self,
        inference: InferenceService,
        storage,
        qwen_client,
    ):
        self._inference = inference
        self._storage = storage
        self._qwen = qwen_client

        self._pipelines: Dict[str, StreamPipeline] = {}
        self._lock = threading.Lock()

        # Cloud calls get their own executor so they cannot occupy the
        # detection threads, plus a semaphore to bound API concurrency.
        self._qwen_executor = ThreadPoolExecutor(
            max_workers=max(1, settings.qwen_max_concurrent) * 2,
            thread_name_prefix="qwen",
        )
        self._qwen_semaphore = threading.Semaphore(
            max(1, settings.qwen_max_concurrent)
        )

        self._shutting_down = False

    # -----------------------------
    # Bulk lifecycle
    # -----------------------------
    def start_enabled_cameras(self) -> None:
        """Called on service boot so enabled cameras resume by themselves."""
        if not settings.auto_start_cameras:
            logger.info("Auto-start disabled; cameras must be started manually.")
            return

        db = SessionLocal()

        try:
            cameras = db.query(Camera).filter(Camera.enabled.is_(True)).all()

            # Detach the values we need; the session closes before the
            # threads start using them.
            targets = [
                (c.id, c.name, c.rtsp_url, c.sample_fps) for c in cameras
            ]

        except Exception as e:
            logger.error(f"Could not load cameras: {e}")
            return

        finally:
            db.close()

        if not targets:
            logger.info("No enabled cameras to start.")
            return

        logger.info(f"Auto-starting {len(targets)} camera(s).")

        for camera_id, name, url, sample_fps in targets:
            try:
                self.start_camera(camera_id, name, url, sample_fps)
            except Exception as e:
                logger.error(f"Failed to auto-start camera {camera_id}: {e}")

    def shutdown(self) -> None:
        self._shutting_down = True

        with self._lock:
            camera_ids = list(self._pipelines.keys())

        for camera_id in camera_ids:
            try:
                self.stop_camera(camera_id)
            except Exception as e:
                logger.warning(f"Error stopping camera {camera_id}: {e}")

        self._qwen_executor.shutdown(wait=False, cancel_futures=True)

        logger.info("Stream manager shut down.")

    # -----------------------------
    # Per-camera lifecycle
    # -----------------------------
    def start_camera(
        self,
        camera_id: str,
        camera_name: str,
        stream_url: str,
        sample_fps: Optional[float] = None,
    ) -> bool:
        """
        Returns True if a new pipeline was started, False if it was already
        running. Raises RuntimeError when the camera limit is reached.
        """
        with self._lock:
            if self._shutting_down:
                raise RuntimeError("Service is shutting down.")

            existing = self._pipelines.get(camera_id)

            if existing is not None and existing.capture.running:
                return False

            if (
                existing is None
                and len(self._pipelines) >= max(1, settings.max_cameras)
            ):
                raise RuntimeError(
                    f"Camera limit reached ({settings.max_cameras}). "
                    "Stop a camera or raise MAX_CAMERAS."
                )

            # Clean up a half-dead pipeline before replacing it.
            if existing is not None:
                existing.analyzer.stop()
                existing.capture.stop()

            capture = CameraCapture(
                camera_id=camera_id,
                stream_url=stream_url,
                on_status_change=lambda status, error: self._on_status_change(
                    camera_id,
                    camera_name,
                    status,
                    error,
                ),
            )

            analyzer = CameraAnalyzer(
                camera_id=camera_id,
                camera_name=camera_name,
                capture=capture,
                inference=self._inference,
                storage=self._storage,
                qwen_client=self._qwen,
                qwen_executor=self._qwen_executor,
                qwen_semaphore=self._qwen_semaphore,
                sample_fps=sample_fps,
            )

            capture.start()
            analyzer.start()

            self._pipelines[camera_id] = StreamPipeline(capture, analyzer)

        logger.info(f"Started camera {camera_id} ({camera_name}).")
        return True

    def stop_camera(self, camera_id: str) -> bool:
        with self._lock:
            pipeline = self._pipelines.pop(camera_id, None)

        if pipeline is None:
            return False

        # Analyzer first, so it can flush open tracks while frames are still
        # available, then the capture thread.
        pipeline.analyzer.stop()
        pipeline.capture.stop()

        self._update_camera_row(camera_id, status="offline", error=None)

        logger.info(f"Stopped camera {camera_id}.")
        return True

    def restart_camera(
        self,
        camera_id: str,
        camera_name: str,
        stream_url: str,
        sample_fps: Optional[float] = None,
    ) -> None:
        self.stop_camera(camera_id)
        self.start_camera(camera_id, camera_name, stream_url, sample_fps)

    # -----------------------------
    # Introspection
    # -----------------------------
    def is_running(self, camera_id: str) -> bool:
        with self._lock:
            pipeline = self._pipelines.get(camera_id)

        return pipeline is not None and pipeline.capture.running

    @property
    def running_count(self) -> int:
        with self._lock:
            return sum(
                1 for p in self._pipelines.values() if p.capture.running
            )

    def camera_status(self, camera_id: str) -> Optional[dict]:
        with self._lock:
            pipeline = self._pipelines.get(camera_id)

        if pipeline is None:
            return None

        return {
            "camera_id": camera_id,
            "running": pipeline.capture.running,
            "capture": pipeline.capture.stats(),
            "analyzer": pipeline.analyzer.stats(),
            "open_tracks": pipeline.analyzer.open_tracks(),
        }

    def all_status(self) -> List[dict]:
        with self._lock:
            camera_ids = list(self._pipelines.keys())

        statuses = []

        for camera_id in camera_ids:
            status = self.camera_status(camera_id)

            if status is not None:
                statuses.append(status)

        return statuses

    def recent_detections(self, camera_id: str, limit: int = 50) -> List[dict]:
        with self._lock:
            pipeline = self._pipelines.get(camera_id)

        if pipeline is None:
            return []

        return pipeline.analyzer.recent_detections(limit)

    # -----------------------------
    # Status propagation
    # -----------------------------
    def _on_status_change(
        self,
        camera_id: str,
        camera_name: str,
        status: str,
        error: Optional[str],
    ) -> None:
        self._update_camera_row(camera_id, status=status, error=error)

        broadcaster.publish(
            {
                "type": "camera.status",
                "camera_id": camera_id,
                "camera_name": camera_name,
                "status": status,
                "error": error,
            }
        )

    def _update_camera_row(
        self,
        camera_id: str,
        *,
        status: str,
        error: Optional[str],
    ) -> None:
        db = SessionLocal()

        try:
            camera = db.query(Camera).filter(Camera.id == camera_id).first()

            if camera is None:
                return

            camera.status = status
            camera.last_error = error[:1024] if error else None

            if status == "online":
                camera.last_frame_at = datetime.utcnow()

            db.commit()

        except Exception as e:
            db.rollback()
            logger.warning(f"Could not update camera {camera_id} status: {e}")

        finally:
            db.close()
