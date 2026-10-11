# app/streaming/visitors.py

"""
Memory of people the system does not know by name.

An unrecognised face used to get a throwaway label that was forgotten two
minutes later, so the same stranger returning every evening looked brand new
each time. The gallery keeps a few face embeddings per stranger, shared by
all cameras and saved to disk, which turns "unknown person" into
"Visitor 7, here for the fourth time since Monday".

Only embeddings and timestamps are stored here, never names. Enrolling the
person under Face Management is what gives them an identity.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from app.core.config import settings

logger = logging.getLogger("nexgen.streaming.visitors")

_MAX_EMBEDDINGS = 5
_MAX_VISITORS = 400
_FORGET_AFTER_SECONDS = 30 * 86400
_SAVE_INTERVAL_SECONDS = 60.0


class VisitorGallery:
    def __init__(self, path: Path, threshold: float, revisit_gap_seconds: float):
        self._path = path
        self._threshold = threshold
        self._revisit_gap = revisit_gap_seconds

        self._lock = threading.Lock()
        self._visitors: Dict[int, dict] = {}
        self._next_id = 1
        self._dirty = False
        self._last_save = time.time()

        self._load()

    # -----------------------------
    # Matching
    # -----------------------------
    def identify(self, embedding: np.ndarray, timestamp: float) -> str:
        """Returns the stable label for this face, creating one if needed."""
        vector = np.asarray(embedding, dtype=np.float32)
        vector = vector / (float(np.linalg.norm(vector)) + 1e-10)

        with self._lock:
            best_id = None
            best_score = -1.0

            for visitor_id, visitor in self._visitors.items():
                score = float(np.max(visitor["embeddings"] @ vector))

                if score > best_score:
                    best_score = score
                    best_id = visitor_id

            if best_id is not None and best_score >= self._threshold:
                visitor = self._visitors[best_id]

                # Coming back after a gap counts as a new visit; staying in
                # view does not.
                if timestamp - visitor["last_seen"] > self._revisit_gap:
                    visitor["visits"] += 1

                visitor["last_seen"] = timestamp

                # Keep a few varied views so the person is still matched
                # from another angle or camera.
                if (
                    len(visitor["embeddings"]) < _MAX_EMBEDDINGS
                    and best_score < 0.85
                ):
                    visitor["embeddings"] = np.vstack(
                        [visitor["embeddings"], vector]
                    )

            else:
                best_id = self._next_id
                self._next_id += 1

                self._visitors[best_id] = {
                    "embeddings": vector.reshape(1, -1),
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "visits": 1,
                }

                self._prune(timestamp)

            self._dirty = True
            self._save_if_due(timestamp)

            return self.label(best_id)

    @staticmethod
    def label(visitor_id: int) -> str:
        return f"Visitor {visitor_id}"

    def info(self, label: str) -> Optional[dict]:
        try:
            visitor_id = int(label.rsplit(" ", 1)[1])
        except (IndexError, ValueError):
            return None

        with self._lock:
            visitor = self._visitors.get(visitor_id)

            if visitor is None:
                return None

            return {
                "label": label,
                "visits": visitor["visits"],
                "first_seen": visitor["first_seen"],
                "last_seen": visitor["last_seen"],
            }

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._visitors)

    # -----------------------------
    # Housekeeping (caller holds the lock)
    # -----------------------------
    def _prune(self, now: float) -> None:
        expired = [
            visitor_id
            for visitor_id, visitor in self._visitors.items()
            if now - visitor["last_seen"] > _FORGET_AFTER_SECONDS
        ]

        for visitor_id in expired:
            del self._visitors[visitor_id]

        if len(self._visitors) > _MAX_VISITORS:
            oldest: List[int] = sorted(
                self._visitors,
                key=lambda visitor_id: self._visitors[visitor_id]["last_seen"],
            )

            for visitor_id in oldest[: len(self._visitors) - _MAX_VISITORS]:
                del self._visitors[visitor_id]

    def _save_if_due(self, now: float) -> None:
        if self._dirty and now - self._last_save >= _SAVE_INTERVAL_SECONDS:
            self._save()

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)

            meta = {
                "next_id": self._next_id,
                "visitors": {
                    str(visitor_id): {
                        "first_seen": visitor["first_seen"],
                        "last_seen": visitor["last_seen"],
                        "visits": visitor["visits"],
                    }
                    for visitor_id, visitor in self._visitors.items()
                },
            }

            arrays = {
                f"v{visitor_id}": visitor["embeddings"]
                for visitor_id, visitor in self._visitors.items()
            }

            tmp_path = self._path.with_suffix(".tmp.npz")

            np.savez_compressed(tmp_path, meta=np.array(json.dumps(meta)), **arrays)
            os.replace(tmp_path, self._path)

            self._dirty = False
            self._last_save = time.time()

        except Exception as e:
            logger.warning(f"Could not save visitor gallery: {e}")

    def flush(self) -> None:
        with self._lock:
            if self._dirty:
                self._save()

    def _load(self) -> None:
        if not self._path.is_file():
            return

        try:
            # allow_pickle stays off: the file holds only arrays and JSON.
            with np.load(self._path, allow_pickle=False) as data:
                meta = json.loads(str(data["meta"]))

                for key, entry in meta["visitors"].items():
                    self._visitors[int(key)] = {
                        "embeddings": np.asarray(data[f"v{key}"], dtype=np.float32),
                        "first_seen": float(entry["first_seen"]),
                        "last_seen": float(entry["last_seen"]),
                        "visits": int(entry["visits"]),
                    }

                self._next_id = int(meta["next_id"])

            logger.info(f"Visitor gallery loaded: {len(self._visitors)} visitor(s).")

        except Exception as e:
            logger.warning(f"Visitor gallery unreadable, starting empty: {e}")
            self._visitors = {}
            self._next_id = 1


_gallery: Optional[VisitorGallery] = None
_gallery_lock = threading.Lock()


def get_visitor_gallery() -> VisitorGallery:
    """One gallery for the whole site, shared by every camera's analyzer."""
    global _gallery

    with _gallery_lock:
        if _gallery is None:
            _gallery = VisitorGallery(
                Path(settings.local_storage_dir) / "visitors.npz",
                settings.unknown_face_cluster_threshold,
                settings.visitor_revisit_gap_seconds,
            )

        return _gallery
