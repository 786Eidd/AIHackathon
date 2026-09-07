# app/services/runtime.py

"""
Process-wide singletons.

Models are loaded once here and shared by every camera pipeline, which is the
whole point of running the streams in one process: a second copy of FaceNet
plus YOLO per camera would exhaust an edge device's memory almost immediately.

The shared instances are handed to an InferenceService that serializes access,
because none of the underlying models tolerate concurrent calls.
"""

import logging
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.integrations.qwen import QwenClient
from app.integrations.storage import StorageClient
from app.pipelines.weapon_detector import WeaponDetector
from app.streaming.inference import InferenceService
from app.streaming.manager import StreamManager

logger = logging.getLogger("nexgen.runtime")

_storage: Optional[StorageClient] = None
_face_embedder = None
_identity_store = None
_weapon_detector: Optional[WeaponDetector] = None
_qwen_client: Optional[QwenClient] = None
_inference: Optional[InferenceService] = None
_stream_manager: Optional[StreamManager] = None


def _load_identity_store(storage: StorageClient):
    from app.face import IdentityStore

    try:
        if settings.face_store_oss_key:
            local_path = storage.download_to_cache(settings.face_store_oss_key)

            if Path(local_path).exists():
                return IdentityStore.load(local_path)

        if settings.face_store_path:
            path = Path(settings.face_store_path)

            if path.exists():
                return IdentityStore.load(path)

    except Exception as e:
        logger.warning(f"Failed to load identity store: {e}")

    return IdentityStore()


def init_runtime() -> None:
    global _storage
    global _face_embedder
    global _identity_store
    global _weapon_detector
    global _qwen_client
    global _inference
    global _stream_manager

    _storage = StorageClient()

    try:
        from app.face import FaceEmbedder

        logger.info(
            f"Initializing FaceEmbedder on device: {settings.computed_device}"
        )

        _face_embedder = FaceEmbedder(
            device=settings.computed_device,
            min_face_size=settings.face_min_size,
        )

        _identity_store = _load_identity_store(_storage)

        logger.info(
            f"Identity store loaded with "
            f"{len(_identity_store.list_identities())} identities"
        )

    except Exception as e:
        logger.error(f"Face module initialization failed: {e}")
        _face_embedder = None
        _identity_store = None

    try:
        _weapon_detector = WeaponDetector(_storage)
    except Exception as e:
        logger.error(f"Weapon detector initialization failed: {e}")
        _weapon_detector = None

    _qwen_client = QwenClient()

    _inference = InferenceService(
        face_embedder=_face_embedder,
        identity_store=_identity_store,
        weapon_detector=_weapon_detector,
    )

    _stream_manager = StreamManager(
        inference=_inference,
        storage=_storage,
        qwen_client=_qwen_client,
    )

    logger.info("Runtime initialization complete")


def shutdown_runtime() -> None:
    global _stream_manager

    if _stream_manager is not None:
        _stream_manager.shutdown()


def reload_identity_store():
    """
    Swaps in a freshly loaded store. The InferenceService is told about the
    new instance under its own lock, so analyzer threads mid-match are not
    reading a half-replaced object.
    """
    global _identity_store

    if _storage is None:
        init_runtime()

    _identity_store = _load_identity_store(_storage)

    if _inference is not None:
        _inference.swap_identity_store(_identity_store)

    return _identity_store


def get_storage() -> Optional[StorageClient]:
    return _storage


def get_face_embedder():
    return _face_embedder


def get_identity_store():
    return _identity_store


def get_weapon_detector() -> Optional[WeaponDetector]:
    return _weapon_detector


def get_qwen_client() -> Optional[QwenClient]:
    return _qwen_client


def get_inference() -> Optional[InferenceService]:
    return _inference


def get_stream_manager() -> Optional[StreamManager]:
    return _stream_manager
