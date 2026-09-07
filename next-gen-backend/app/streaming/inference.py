# app/streaming/inference.py

"""
Shared, thread-safe access to the detection models.

The models are loaded exactly once and shared by every camera's analyzer
thread. Neither MTCNN nor the Ultralytics predictor is safe to call
concurrently on the same instance — they keep internal buffers across a call
— so each model is guarded by its own lock. Using separate locks (rather than
one global one) means one camera's face pass can overlap another's weapon
pass, which is where most of the practical concurrency comes from.

A semaphore on top bounds how much detection work is in flight at once, so
adding cameras degrades throughput gracefully instead of exhausting VRAM.
"""

from __future__ import annotations

import logging
import threading
from typing import List, Optional, Tuple

import numpy as np

from app.core.config import settings

logger = logging.getLogger("nexgen.streaming.inference")


class InferenceService:
    def __init__(
        self,
        face_embedder,
        identity_store,
        weapon_detector,
    ):
        self._face_embedder = face_embedder
        self._identity_store = identity_store
        self._weapon_detector = weapon_detector

        self._face_lock = threading.Lock()
        self._weapon_lock = threading.Lock()

        # Reentrant because the store is swapped wholesale on enrollment
        # reload while analyzer threads are matching against it.
        self._identity_lock = threading.RLock()

        self._gpu_semaphore = threading.Semaphore(
            max(1, settings.inference_max_concurrent)
        )

    # -----------------------------
    # Identity store
    # -----------------------------
    def swap_identity_store(self, identity_store) -> None:
        with self._identity_lock:
            self._identity_store = identity_store

    @property
    def identity_count(self) -> int:
        with self._identity_lock:
            if self._identity_store is None:
                return 0

            return len(self._identity_store.list_identities())

    @property
    def face_available(self) -> bool:
        return self._face_embedder is not None and self._identity_store is not None

    @property
    def weapon_available(self) -> bool:
        return self._weapon_detector is not None and self._weapon_detector.loaded

    # -----------------------------
    # Frame scaling
    #
    # Inference runs on a downscaled copy and boxes are mapped back to native
    # coordinates, so crops and annotations stay full resolution.
    # -----------------------------
    @staticmethod
    def prepare_frame(frame: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Returns (frame_for_inference, scale) where multiplying a box from the
        inference frame by `scale` maps it back onto the original frame.
        """
        target_width = int(settings.stream_inference_width or 0)

        if target_width <= 0:
            return frame, 1.0

        height, width = frame.shape[:2]

        if width <= target_width:
            return frame, 1.0

        import cv2

        scale_down = target_width / float(width)
        target_height = max(1, int(round(height * scale_down)))

        resized = cv2.resize(
            frame,
            (target_width, target_height),
            interpolation=cv2.INTER_AREA,
        )

        return resized, 1.0 / scale_down

    # -----------------------------
    # Face detection + matching
    # -----------------------------
    def detect_faces(
        self,
        frame: np.ndarray,
        face_threshold: float,
    ) -> List[dict]:
        """
        Detects every face in `frame`, matches it against the identity store
        and returns detections in *original frame* coordinates.

        Faces below the configured detection confidence or pixel size are
        dropped here so downstream code never sees them.
        """
        if not self.face_available:
            return []

        import cv2
        from PIL import Image

        inference_frame, scale = self.prepare_frame(frame)

        try:
            rgb = cv2.cvtColor(inference_frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb)
        except Exception as e:
            logger.warning(f"Frame conversion failed: {e}")
            return []

        with self._gpu_semaphore:
            with self._face_lock:
                try:
                    faces = self._face_embedder.detect_and_embed(pil_image)
                except Exception as e:
                    logger.warning(f"Face inference failed: {e}")
                    return []

        results = []

        for box, embedding, detection_confidence in faces:
            if detection_confidence < settings.face_min_confidence:
                continue

            try:
                x1, y1, x2, y2 = [float(v) * scale for v in box]
            except Exception:
                continue

            # Size gate is applied in native pixels so the threshold means
            # the same thing regardless of the inference downscale.
            if (
                x2 - x1
            ) < settings.face_min_size or (y2 - y1) < settings.face_min_size:
                continue

            with self._identity_lock:
                try:
                    identity_name, similarity_score = self._identity_store.match(
                        embedding,
                        threshold=face_threshold,
                    )
                except Exception as e:
                    logger.warning(f"Identity match failed: {e}")
                    continue

            results.append(
                {
                    "bbox": [x1, y1, x2, y2],
                    "detection_confidence": float(detection_confidence),
                    "identity_name": identity_name,
                    "status": "unknown" if identity_name == "unknown" else "known",
                    "similarity_score": float(similarity_score),
                    "embedding": embedding,
                }
            )

        return results

    # -----------------------------
    # Weapon detection
    # -----------------------------
    def detect_weapons(
        self,
        frame: np.ndarray,
        confidence_threshold: float,
    ) -> List[dict]:
        if not self.weapon_available:
            return []

        inference_frame, scale = self.prepare_frame(frame)

        with self._gpu_semaphore:
            with self._weapon_lock:
                try:
                    detections = self._weapon_detector.detect(
                        inference_frame,
                        confidence_threshold,
                        settings.weapon_iou_threshold,
                    )
                except Exception as e:
                    logger.warning(f"Weapon inference failed: {e}")
                    return []

        if scale == 1.0:
            return detections

        for det in detections:
            try:
                det["bbox"] = [float(v) * scale for v in det["bbox"]]
            except Exception:
                continue

        return detections
