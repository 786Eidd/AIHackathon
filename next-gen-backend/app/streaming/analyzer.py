# app/streaming/analyzer.py

"""
Per-camera analysis loop.

One of these runs per camera, on its own thread, alongside that camera's
capture thread. It paces itself to the target sample rate, takes whatever the
newest decoded frame is, runs the detectors, feeds the tracker, and persists
plus broadcasts anything that turns into an event.

Two rules shape the code:

  * The loop never blocks on anything slow. Cloud VLM calls and clip encoding
    are handed to background executors; a stalled DashScope request must not
    stop weapon detection.
  * The loop never raises out. A camera with a wedged codec or a transient DB
    lock logs and keeps going, because one bad camera must not take down the
    other seven.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from app.core.config import settings
from app.core.timeutil import iso_utc
from app.db.models import Alert, Event
from app.db.session import SessionLocal
from app.pipelines import fusion_engine
from app.pipelines.appearance import clothing_colour, describe_unknown
from app.pipelines.prompts import (
    APPEARANCE_PROMPT,
    FRAME_ANALYSIS_PROMPT,
    TEMPORAL_EVENT_PROMPT,
)
from app.streaming.broadcaster import broadcaster
from app.streaming.capture import CameraCapture
from app.streaming.clips import (
    ClipRecorder,
    FrameRingBuffer,
    clip_playback_fps,
    clips_enabled,
)
from app.streaming.tracker import LiveEventTracker
from app.streaming.visitors import get_visitor_gallery

logger = logging.getLogger("nexgen.streaming.analyzer")


def _utc(epoch_seconds: float) -> datetime:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).replace(tzinfo=None)


def _encode_jpeg(frame: np.ndarray) -> Optional[bytes]:
    import cv2

    ok, buffer = cv2.imencode(".jpg", frame)

    if not ok:
        return None

    return buffer.tobytes()


def _crop(frame: np.ndarray, box) -> Optional[np.ndarray]:
    height, width = frame.shape[:2]

    try:
        x1, y1, x2, y2 = [float(v) for v in box]
    except Exception:
        return None

    x1 = max(0, int(x1))
    y1 = max(0, int(y1))
    x2 = min(width, int(x2))
    y2 = min(height, int(y2))

    if x2 <= x1 or y2 <= y1:
        return None

    return frame[y1:y2, x1:x2]


def _draw_boxes(frame: np.ndarray, detections: List[dict]) -> np.ndarray:
    import cv2

    annotated = frame.copy()

    for det in detections:
        try:
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]

            label = f"{det['object_class']} {det['confidence']:.2f}"

            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)

            cv2.putText(
                annotated,
                label,
                (x1, max(0, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                2,
            )
        except Exception:
            continue

    return annotated


class CameraAnalyzer:
    def __init__(
        self,
        camera_id: str,
        camera_name: str,
        capture: CameraCapture,
        inference,
        storage,
        qwen_client,
        qwen_executor: ThreadPoolExecutor,
        qwen_semaphore: threading.Semaphore,
        sample_fps: Optional[float] = None,
    ):
        self.camera_id = camera_id
        self.camera_name = camera_name

        self._capture = capture
        self._inference = inference
        self._storage = storage
        self._qwen = qwen_client
        self._qwen_executor = qwen_executor
        self._qwen_semaphore = qwen_semaphore

        self.sample_fps = float(sample_fps or settings.stream_sample_fps)

        if self.sample_fps <= 0:
            self.sample_fps = 1.0

        self._tracker = LiveEventTracker(camera_id)
        self._visitors = get_visitor_gallery()

        self._ring_buffer = FrameRingBuffer(
            settings.clip_pre_seconds,
            self.sample_fps,
        )

        self._recorders: List[ClipRecorder] = []

        # Bounded history of raw detections, exposed over the API instead of
        # being written to the database.
        self._detection_log: List[dict] = []
        self._detection_lock = threading.Lock()

        self._alert_cooldowns: Dict[str, float] = {}
        self._alert_lock = threading.Lock()

        # Evidence throttles: last save time per face label, and the last
        # annotated weapon frame.
        self._crop_saved_at: Dict[str, float] = {}
        self._last_annotated: tuple = (0.0, None, None)
        self._last_weapons: tuple = (0.0, [])

        # (timestamp, faces, weapons) from the newest analysed frame, drawn
        # onto the browser preview.
        self._overlay: Optional[tuple] = None
        self._last_scene_check = 0.0

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._frames_analyzed = 0
        self._last_analyzed_seq = -1
        self._last_analysis_at: Optional[float] = None

    # -----------------------------
    # Lifecycle
    # -----------------------------
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run,
            name=f"analyzer-{self.camera_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 15.0) -> None:
        self._stop_event.set()

        thread = self._thread

        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)

        self._thread = None

        # Flush anything still open so events do not dangle in "open" state
        # forever after a camera is taken down.
        for track in self._tracker.close_all():
            try:
                self._handle_closed_track(track)
            except Exception as e:
                logger.warning(f"[{self.camera_id}] Flush on stop failed: {e}")

        for recorder in list(self._recorders):
            recorder.finalize()

        self._recorders.clear()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stats(self) -> dict:
        return {
            "sample_fps": self.sample_fps,
            "frames_analyzed": self._frames_analyzed,
            "open_tracks": len(self._tracker.snapshot()),
            "unknown_tracks": self._visitors.count,
            "active_clip_recorders": len(self._recorders),
            "last_analysis_age_seconds": (
                round(time.time() - self._last_analysis_at, 2)
                if self._last_analysis_at
                else None
            ),
        }

    def recent_detections(self, limit: int = 50) -> List[dict]:
        with self._detection_lock:
            return self._detection_log[-limit:]

    def open_tracks(self) -> List[dict]:
        return self._tracker.snapshot()

    def overlay(self) -> Optional[tuple]:
        return self._overlay

    # -----------------------------
    # Main loop
    # -----------------------------
    def _run(self) -> None:
        interval = 1.0 / self.sample_fps

        logger.info(
            f"[{self.camera_id}] Analyzer started at {self.sample_fps:.2f} fps."
        )

        while not self._stop_event.is_set():
            cycle_start = time.monotonic()

            try:
                self._tick()
            except Exception as e:
                logger.exception(f"[{self.camera_id}] Analysis tick failed: {e}")

            elapsed = time.monotonic() - cycle_start

            # If inference is slower than the target rate we simply run as
            # fast as we can; the capture layer keeps discarding stale frames
            # so we never fall behind real time.
            if self._stop_event.wait(max(0.0, interval - elapsed)):
                break

        logger.info(f"[{self.camera_id}] Analyzer stopped.")

    def _tick(self) -> None:
        now = time.time()

        # Close tracks that have gone quiet even if no frame arrived, so a
        # dead camera still finalizes its events.
        for track in self._tracker.close_stale(now):
            self._handle_closed_track(track)

        self._reap_recorders()

        latest = self._capture.read_latest()

        if latest is None:
            return

        frame_seq, timestamp, frame = latest

        # Nothing new decoded since the last tick; re-running the detectors on
        # an identical frame would only waste GPU time.
        if frame_seq == self._last_analyzed_seq:
            return

        self._last_analyzed_seq = frame_seq
        self._frames_analyzed += 1
        self._last_analysis_at = now

        self._feed_recorders(timestamp, self._ring_buffer.add(timestamp, frame))

        face_detections = self._process_faces(frame, timestamp)

        if self._frames_analyzed % max(1, settings.weapon_every_n_frames) == 0:
            weapon_detections = self._process_weapons(frame, timestamp)
            self._last_weapons = (timestamp, weapon_detections)
        else:
            weapon_detections = []

        # On frames where the object detector was skipped, keep drawing the
        # boxes from its last pass so they do not flicker in the live view.
        last_weapon_time, last_weapons = self._last_weapons
        shown_weapons = (
            weapon_detections
            if weapon_detections or timestamp - last_weapon_time > 1.0
            else last_weapons
        )

        self._overlay = (timestamp, face_detections, shown_weapons)

        self._record_detections(timestamp, face_detections, weapon_detections)

        self._maybe_scene_check(frame, timestamp)

    # -----------------------------
    # Face pipeline
    # -----------------------------
    def _process_faces(self, frame: np.ndarray, timestamp: float) -> List[dict]:
        detections = self._inference.detect_faces(
            frame,
            settings.face_match_threshold,
        )

        if not detections:
            return []

        published = []

        for detection in detections:
            # Give unrecognised faces a stable label, otherwise every frame
            # looks like a brand new stranger and no track can ever merge.
            if detection["status"] == "unknown":
                detection["identity_name"] = self._visitors.identify(
                    detection["embedding"],
                    timestamp,
                )

            crop_key, crop_ref = self._save_face_crop(
                frame,
                detection,
                timestamp,
            )

            detection["crop_key"] = crop_key
            detection["crop_ref"] = crop_ref

            opened, closed = self._tracker.observe_face(detection, timestamp)

            if closed is not None:
                self._handle_closed_track(closed)

            if opened is not None:
                self._handle_opened_track(opened, frame, timestamp)

            published.append(
                {
                    "identity_name": detection["identity_name"],
                    "status": detection["status"],
                    "similarity_score": round(detection["similarity_score"], 4),
                    "detection_confidence": round(
                        detection["detection_confidence"], 4
                    ),
                    "bbox": [round(float(v), 1) for v in detection["bbox"]],
                    "crop_key": crop_key,
                }
            )

        return published

    def _save_face_crop(
        self,
        frame: np.ndarray,
        detection: dict,
        timestamp: float,
    ):
        label = detection["identity_name"]

        # One crop per subject every few seconds is plenty of evidence; one
        # per analysed frame fills the disk within days.
        last = self._crop_saved_at.get(label)

        if (
            last is not None
            and timestamp - last < settings.face_crop_interval_seconds
        ):
            return None, None

        crop = _crop(frame, detection["bbox"])

        if crop is None:
            return None, None

        if len(self._crop_saved_at) > 512:
            self._crop_saved_at.clear()

        self._crop_saved_at[label] = timestamp

        key = self._artifact_key(
            "face_crops",
            f"{label.replace(' ', '_')}_{int(timestamp * 1000)}.jpg",
        )

        return self._save_image(key, crop)

    # -----------------------------
    # Weapon pipeline
    # -----------------------------
    def _process_weapons(self, frame: np.ndarray, timestamp: float) -> List[dict]:
        detections = self._inference.detect_weapons(
            frame,
            settings.weapon_confidence_threshold,
        )

        if not detections:
            return []

        annotated = _draw_boxes(frame, detections)

        last_saved, annotated_key, annotated_ref = self._last_annotated

        if timestamp - last_saved >= settings.annotated_frame_interval_seconds:
            annotated_key, annotated_ref = self._save_image(
                self._artifact_key("annotated", f"{int(timestamp * 1000)}.jpg"),
                annotated,
            )
            self._last_annotated = (timestamp, annotated_key, annotated_ref)

        published = []

        for detection in detections:
            detection["annotated_frame_key"] = annotated_key
            detection["annotated_frame_ref"] = annotated_ref

            opened, closed = self._tracker.observe_weapon(detection, timestamp)

            if closed is not None:
                self._handle_closed_track(closed)

            if opened is not None:
                self._handle_opened_track(opened, annotated, timestamp)

            published.append(
                {
                    "object_class": detection["object_class"],
                    "raw_class": detection.get("raw_class"),
                    "confidence": round(float(detection["confidence"]), 4),
                    "bbox": [round(float(v), 1) for v in detection["bbox"]],
                    "annotated_frame_key": annotated_key,
                }
            )

        return published

    # -----------------------------
    # Track -> event -> alert
    # -----------------------------
    def _handle_opened_track(
        self,
        track: dict,
        frame: np.ndarray,
        timestamp: float,
    ) -> None:
        open_tracks = self._tracker.snapshot()

        if track.get("kind") == "face":
            weapon_tracks = [t for t in open_tracks if t.get("kind") == "weapon"]
            scored = fusion_engine.fuse_face_event(track, weapon_tracks)
        else:
            face_tracks = [t for t in open_tracks if t.get("kind") == "face"]
            scored = fusion_engine.fuse_weapon_event(track, face_tracks)

        appearance = None

        if track.get("kind") == "face" and track.get("status") == "unknown":
            appearance = self._describe_unknown(track, frame)

            if appearance["text"]:
                scored["summary"] = f"{scored['summary']} {appearance['text']}"

        snapshot_key, _ = self._save_image(
            self._artifact_key(
                "events",
                f"{scored['event_type']}_{int(timestamp * 1000)}.jpg",
            ),
            frame,
        )

        event = self._create_event(
            event_type=scored["event_type"],
            risk_level=scored["risk_level"],
            summary=scored["summary"],
            started_at=track["first_seen"],
            payload={
                "track_id": track["track_id"],
                "track_key": track["key"],
                "kind": track.get("kind"),
                "identity_name": track.get("identity_name"),
                "status": track.get("status"),
                "object_class": track.get("object_class"),
                "best_similarity_score": track.get("best_similarity_score"),
                "max_confidence": track.get("max_confidence"),
                "bbox": track.get("bbox"),
                "appearance": appearance,
            },
            snapshot_key=snapshot_key,
        )

        if event is None:
            return

        self._tracker.bind_event_id(track["track_id"], event["event_id"])

        if appearance is not None:
            self._schedule_appearance(event, snapshot_key)

        broadcaster.publish(
            {
                "type": "event.opened",
                "camera_id": self.camera_id,
                "camera_name": self.camera_name,
                "event": event,
            }
        )

        if fusion_engine.should_alert(scored["risk_level"]):
            self._raise_alert(event)

        if scored["risk_level"] in ("high", "medium"):
            self._start_clip(event["event_id"], timestamp)

        if scored["risk_level"] == "high":
            self._schedule_event_analysis(event)

    def _describe_unknown(self, track: dict, frame: np.ndarray) -> dict:
        """What can be said about a stranger: clothing colour and history."""
        label = track.get("identity_name") or "unknown"
        profile = self._visitors.info(label) or {}

        colour = None

        try:
            colour = clothing_colour(frame, track.get("bbox"))
        except Exception as e:
            logger.debug(f"[{self.camera_id}] Clothing colour failed: {e}")

        visits = int(profile.get("visits", 1))
        first_seen = profile.get("first_seen")

        return {
            "label": label,
            "visits": visits,
            "first_seen": iso_utc(_utc(first_seen)) if first_seen else None,
            "clothing_colour": colour,
            "text": describe_unknown(label, visits, first_seen, colour),
        }

    def _handle_closed_track(self, track: dict) -> None:
        event_id = track.get("event_id")

        if not event_id:
            return

        db = SessionLocal()

        try:
            event = db.query(Event).filter(Event.id == event_id).first()

            if event is None:
                return

            event.status = "closed"
            event.ended_at = _utc(track["last_seen"])
            event.detection_count = track.get("detection_count", 1)

            payload = dict(event.payload or {})
            payload["duration_seconds"] = round(
                track["last_seen"] - track["first_seen"],
                2,
            )
            event.payload = payload

            db.commit()

            broadcaster.publish(
                {
                    "type": "event.closed",
                    "camera_id": self.camera_id,
                    "camera_name": self.camera_name,
                    "event": {
                        "event_id": event_id,
                        "event_type": event.event_type,
                        "risk_level": event.risk_level,
                        "detection_count": event.detection_count,
                        "duration_seconds": payload["duration_seconds"],
                        "ended_at": iso_utc(event.ended_at),
                    },
                }
            )

        except Exception as e:
            db.rollback()
            logger.warning(f"[{self.camera_id}] Failed to close event: {e}")

        finally:
            db.close()

    def _create_event(
        self,
        *,
        event_type: str,
        risk_level: str,
        summary: str,
        started_at: float,
        payload: dict,
        snapshot_key: Optional[str],
    ) -> Optional[dict]:
        import uuid

        event_id = f"evt_{uuid.uuid4().hex[:12]}"

        db = SessionLocal()

        try:
            event = Event(
                id=event_id,
                camera_id=self.camera_id,
                event_type=event_type,
                risk_level=risk_level,
                status="open",
                started_at=_utc(started_at),
                detection_count=1,
                summary=summary,
                payload=payload,
                snapshot_key=snapshot_key,
            )

            db.add(event)
            db.commit()

            return {
                "event_id": event_id,
                "camera_id": self.camera_id,
                "event_type": event_type,
                "risk_level": risk_level,
                "status": "open",
                "started_at": iso_utc(_utc(started_at)),
                "summary": summary,
                "snapshot_key": snapshot_key,
                "snapshot_url": self._storage.public_url(snapshot_key),
                "payload": payload,
            }

        except Exception as e:
            db.rollback()
            logger.warning(f"[{self.camera_id}] Failed to create event: {e}")
            return None

        finally:
            db.close()

    def _raise_alert(self, event: dict) -> None:
        cooldown_key = event["event_type"]
        now = time.time()

        # Scene-check alerts arrive from the Qwen executor, so the cooldown
        # table is shared between threads.
        with self._alert_lock:
            last = self._alert_cooldowns.get(cooldown_key)

            # A stranger loitering would otherwise generate an alert every few
            # seconds; the event history still records every occurrence.
            if last is not None and now - last < settings.alert_cooldown_seconds:
                return

            self._alert_cooldowns[cooldown_key] = now

        alert = fusion_engine.build_alert(event)

        created_at = datetime.utcnow()

        # Clients sort and age alerts by these, so the pushed copy must carry
        # the same fields the REST listing does.
        alert["created_at"] = iso_utc(created_at)
        alert["acknowledged"] = False
        alert["snapshot_url"] = event.get("snapshot_url")

        db = SessionLocal()

        try:
            row = Alert(
                id=alert["alert_id"],
                event_id=event["event_id"],
                camera_id=self.camera_id,
                priority=alert["priority"],
                title=alert["title"],
                message=alert["message"],
                recommended_action=alert["recommended_action"],
                created_at=created_at,
            )

            db.add(row)
            db.commit()

        except Exception as e:
            db.rollback()
            logger.warning(f"[{self.camera_id}] Failed to persist alert: {e}")
            return

        finally:
            db.close()

        broadcaster.publish(
            {
                "type": "alert",
                "camera_id": self.camera_id,
                "camera_name": self.camera_name,
                "alert": alert,
            }
        )

        logger.info(
            f"[{self.camera_id}] {alert['priority']} alert: {alert['title']}"
        )

        # The template message just went out; try to improve the wording
        # off-thread and push an update if it lands.
        self._schedule_alert_enrichment(alert, event)

    # -----------------------------
    # Evidence clips
    # -----------------------------
    def _start_clip(self, event_id: str, timestamp: float) -> None:
        if not clips_enabled():
            return

        recorder = ClipRecorder(
            event_id=event_id,
            camera_id=self.camera_id,
            storage_key=self._artifact_key("clips", f"{event_id}.webm"),
            pre_roll=self._ring_buffer.snapshot(),
            started_at=timestamp,
            post_seconds=settings.clip_post_seconds,
            playback_fps=clip_playback_fps(self.sample_fps),
            storage=self._storage,
            on_complete=self._attach_clip,
        )

        self._recorders.append(recorder)

    def _feed_recorders(self, timestamp: float, frame: np.ndarray) -> None:
        for recorder in list(self._recorders):
            recorder.add_frame(timestamp, frame)

    def _reap_recorders(self) -> None:
        self._recorders = [r for r in self._recorders if not r.finalized]

    def _attach_clip(self, event_id: str, clip_key: str) -> None:
        db = SessionLocal()

        try:
            event = db.query(Event).filter(Event.id == event_id).first()

            if event is None:
                return

            event.clip_key = clip_key
            db.commit()

            broadcaster.publish(
                {
                    "type": "event.clip_ready",
                    "camera_id": self.camera_id,
                    "event_id": event_id,
                    "clip_key": clip_key,
                    "clip_url": self._storage.public_url(clip_key),
                }
            )

        except Exception as e:
            db.rollback()
            logger.warning(f"[{self.camera_id}] Failed to attach clip: {e}")

        finally:
            db.close()

    # -----------------------------
    # Qwen (always off the analysis thread)
    # -----------------------------
    def _qwen_enabled(self) -> bool:
        return self._qwen is not None and self._qwen.enabled

    def _submit_qwen(self, fn, *args) -> None:
        try:
            self._qwen_executor.submit(fn, *args)
        except RuntimeError:
            # Executor already shutting down.
            pass

    def _maybe_scene_check(self, frame: np.ndarray, timestamp: float) -> None:
        if not settings.enable_qwen_scene_polling or not self._qwen_enabled():
            return

        if timestamp - self._last_scene_check < settings.qwen_scene_interval_seconds:
            return

        self._last_scene_check = timestamp

        key = self._artifact_key("scene", f"{int(timestamp * 1000)}.jpg")

        stored_key, image_ref = self._save_image(key, frame)

        if not image_ref:
            return

        self._submit_qwen(self._run_scene_check, image_ref, stored_key, timestamp)

    def _run_scene_check(
        self,
        image_ref: str,
        snapshot_key: Optional[str],
        timestamp: float,
    ) -> None:
        with self._qwen_semaphore:
            try:
                analysis = self._qwen.analyze_image(image_ref, FRAME_ANALYSIS_PROMPT)
            except Exception as e:
                logger.warning(f"[{self.camera_id}] Scene analysis failed: {e}")
                return

        if not analysis:
            return

        scored = fusion_engine.fuse_scene_analysis(analysis, timestamp)

        if scored is None:
            return

        event = self._create_event(
            event_type=scored["event_type"],
            risk_level=scored["risk_level"],
            summary=scored["summary"],
            started_at=timestamp,
            payload={"source": "qwen_scene", "analysis": analysis},
            snapshot_key=snapshot_key,
        )

        if event is None:
            return

        # Scene checks are point-in-time, so the event has no track to close
        # it later; mark it closed immediately.
        self._close_event_now(event["event_id"], timestamp)

        broadcaster.publish(
            {
                "type": "event.opened",
                "camera_id": self.camera_id,
                "camera_name": self.camera_name,
                "event": event,
            }
        )

        if fusion_engine.should_alert(scored["risk_level"]):
            self._raise_alert(event)

    def _schedule_event_analysis(self, event: dict) -> None:
        if not settings.enable_qwen_event_analysis or not self._qwen_enabled():
            return

        if not settings.enable_qwen_temporal:
            return

        # The pre-roll buffer already holds the run-up to this event, which is
        # exactly the sequence a temporal model needs.
        frames = self._ring_buffer.snapshot()

        if not frames:
            return

        refs = []

        max_refs = max(1, settings.qwen_max_images_per_temporal_call)

        for index, (frame_ts, frame) in enumerate(frames[-max_refs:]):
            key = self._artifact_key(
                f"temporal/{event['event_id']}",
                f"{index:02d}.jpg",
            )

            _, ref = self._save_image(key, frame)

            if ref:
                refs.append(ref)

        if not refs:
            return

        self._submit_qwen(self._run_event_analysis, event, refs)

    def _run_event_analysis(self, event: dict, image_refs: List[str]) -> None:
        with self._qwen_semaphore:
            try:
                analysis = self._qwen.analyze_video_frames(
                    image_refs,
                    TEMPORAL_EVENT_PROMPT,
                )
            except Exception as e:
                logger.warning(f"[{self.camera_id}] Temporal analysis failed: {e}")
                return

        if not analysis:
            return

        interpretation = fusion_engine.fuse_temporal_analysis(analysis)

        db = SessionLocal()

        try:
            row = db.query(Event).filter(Event.id == event["event_id"]).first()

            if row is None:
                return

            payload = dict(row.payload or {})
            payload["temporal_analysis"] = analysis
            row.payload = payload

            if interpretation is not None:
                row.summary = f"{row.summary}\n\n{interpretation['summary']}"

            db.commit()

            summary = row.summary

        except Exception as e:
            db.rollback()
            logger.warning(f"[{self.camera_id}] Failed to store analysis: {e}")
            return

        finally:
            db.close()

        broadcaster.publish(
            {
                "type": "event.analysis",
                "camera_id": self.camera_id,
                "event_id": event["event_id"],
                "analysis": analysis,
                "summary": summary,
            }
        )

    def _schedule_appearance(self, event: dict, snapshot_key: Optional[str]) -> None:
        """Asks the vision model for a fuller description, when one is set up."""
        if not self._qwen_enabled() or not snapshot_key:
            return

        image_ref = self._storage.access_reference(snapshot_key)

        if image_ref:
            self._submit_qwen(self._run_appearance, event, image_ref)

    def _run_appearance(self, event: dict, image_ref: str) -> None:
        with self._qwen_semaphore:
            try:
                result = self._qwen.analyze_image(image_ref, APPEARANCE_PROMPT)
            except Exception as e:
                logger.warning(f"[{self.camera_id}] Appearance analysis failed: {e}")
                return

        description = (result or {}).get("description")

        if not description or not isinstance(description, str):
            return

        db = SessionLocal()

        try:
            row = db.query(Event).filter(Event.id == event["event_id"]).first()

            if row is None:
                return

            payload = dict(row.payload or {})
            appearance = dict(payload.get("appearance") or {})
            appearance["description"] = description.strip()
            payload["appearance"] = appearance
            row.payload = payload
            row.summary = f"{row.summary}\n\n{description.strip()}"

            db.commit()

            summary = row.summary

        except Exception as e:
            db.rollback()
            logger.warning(f"[{self.camera_id}] Failed to store appearance: {e}")
            return

        finally:
            db.close()

        broadcaster.publish(
            {
                "type": "event.analysis",
                "camera_id": self.camera_id,
                "event_id": event["event_id"],
                "analysis": {"appearance": description.strip()},
                "summary": summary,
            }
        )

    def _schedule_alert_enrichment(self, alert: dict, event: dict) -> None:
        if not self._qwen_enabled():
            return

        self._submit_qwen(self._run_alert_enrichment, alert, event)

    def _run_alert_enrichment(self, alert: dict, event: dict) -> None:
        with self._qwen_semaphore:
            message = fusion_engine.enrich_alert_message(event, self._qwen)

        if not message:
            return

        db = SessionLocal()

        try:
            row = db.query(Alert).filter(Alert.id == alert["alert_id"]).first()

            if row is None:
                return

            row.message = message
            db.commit()

        except Exception as e:
            db.rollback()
            logger.warning(f"[{self.camera_id}] Failed to update alert: {e}")
            return

        finally:
            db.close()

        broadcaster.publish(
            {
                "type": "alert.updated",
                "camera_id": self.camera_id,
                "alert_id": alert["alert_id"],
                "message": message,
            }
        )

    def _close_event_now(self, event_id: str, timestamp: float) -> None:
        db = SessionLocal()

        try:
            row = db.query(Event).filter(Event.id == event_id).first()

            if row is None:
                return

            row.status = "closed"
            row.ended_at = _utc(timestamp)
            db.commit()

        except Exception as e:
            db.rollback()
            logger.warning(f"[{self.camera_id}] Failed to close event: {e}")

        finally:
            db.close()

    # -----------------------------
    # Detection log + artifacts
    # -----------------------------
    def _record_detections(
        self,
        timestamp: float,
        faces: List[dict],
        weapons: List[dict],
    ) -> None:
        if not faces and not weapons:
            return

        record = {
            "camera_id": self.camera_id,
            "timestamp": timestamp,
            "observed_at": iso_utc(_utc(timestamp)),
            "faces": faces,
            "weapons": weapons,
        }

        limit = max(10, settings.live_detection_buffer_size)

        with self._detection_lock:
            self._detection_log.append(record)

            if len(self._detection_log) > limit:
                del self._detection_log[: len(self._detection_log) - limit]

        broadcaster.publish({"type": "detection", **record})

    def _artifact_key(self, category: str, filename: str) -> str:
        day = datetime.now(tz=timezone.utc).strftime("%Y%m%d")

        return f"artifacts/{self.camera_id}/{day}/{category}/{filename}"

    def _save_image(self, key: str, frame: np.ndarray):
        """Returns (storage_key, access_reference) or (None, None)."""
        data = _encode_jpeg(frame)

        if data is None:
            return None, None

        try:
            self._storage.save_bytes(key, data)
            return key, self._storage.access_reference(key)
        except Exception as e:
            logger.warning(f"[{self.camera_id}] Failed to save {key}: {e}")
            return None, None
