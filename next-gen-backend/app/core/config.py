# app/core/config.py

from functools import cached_property
from typing import List

import torch
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    device: str = "auto"
    log_level: str = "INFO"
    log_json: bool = True
    # "lan" allows localhost and private-network origins, "*" allows any
    # origin, anything else is a comma-separated allow list.
    cors_origins: str = "lan"

    database_url: str = "sqlite:///./nexgen.db"

    storage_backend: str = "local"
    local_storage_dir: str = "storage"

    oss_endpoint: str = ""
    oss_bucket: str = ""
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""

    dashscope_api_key: str = ""

    face_store_path: str = "storage/models/identity_store.pkl"
    face_store_oss_key: str = ""

    face_match_threshold: float = 0.60
    face_min_confidence: float = 0.70
    face_min_size: int = 30

    weapon_model_path: str = "storage/models/weapon_detector.pt"
    weapon_model_oss_key: str = ""

    weapon_confidence_threshold: float = 0.40
    weapon_iou_threshold: float = 0.45

    # Object detection is the most expensive step on a CPU, so it runs on a
    # smaller image and only on every Nth analysed frame. Faces are still
    # checked on every frame.
    weapon_inference_size: int = 480
    weapon_every_n_frames: int = 2

    # -----------------------------
    # Live streaming
    #
    # Defaults are tuned for CUDA-capable edge hardware (Jetson class)
    # running 5-8 cameras on one device. Every value is .env-overridable,
    # so the same code can be throttled down for a CPU-only board.
    # -----------------------------
    max_cameras: int = 8
    auto_start_cameras: bool = True

    # Plug-and-play: on boot, scan the local network and attached devices
    # and register what is found. Recorders and IP cameras need a login, so
    # they are only added unattended when a site-wide one is set here;
    # otherwise they wait for it to be typed into the dashboard.
    auto_discover_on_start: bool = True
    camera_default_username: str = ""
    camera_default_password: str = ""
    discovery_max_channels: int = 16

    # Set to the built dashboard (nextgen-frontend/dist) to serve the UI and
    # the API from this one process, as the appliance does.
    frontend_dist_dir: str = "../nextgen-frontend/dist"

    # Upper bound on frames per second handed to the detectors, per camera.
    # It is a ceiling, not a promise: when the hardware cannot keep up (more
    # cameras, no GPU) each camera simply analyses as often as it gets a turn
    # and the reader thread drops the frames in between.
    stream_sample_fps: float = 8.0

    # Frames are downscaled to this width before inference and boxes are
    # scaled back to native coordinates. 0 disables downscaling. This is the
    # single biggest throughput lever on edge hardware.
    stream_inference_width: int = 960

    # UDP loses packets and produces smeared frames on congested networks;
    # TCP is the safer default for analytics.
    stream_rtsp_transport: str = "tcp"
    stream_socket_timeout_seconds: float = 10.0

    # If no frame arrives within this window the connection is considered
    # dead even though the socket is still open (a common CCTV failure mode).
    stream_read_stall_seconds: float = 15.0

    stream_reconnect_initial_seconds: float = 2.0
    stream_reconnect_max_seconds: float = 60.0

    # Bounds concurrent detector calls so N cameras cannot exhaust VRAM.
    inference_max_concurrent: int = 2

    # -----------------------------
    # Live event tracking
    # -----------------------------
    # A track survives this long without a new detection before it is
    # closed. Larger values merge more aggressively across brief occlusions.
    event_gap_seconds: float = 3.0

    # Suppresses repeat alerts of the same type on the same camera.
    alert_cooldown_seconds: float = 30.0

    # How long an unclaimed unknown-face label stays reusable.
    unknown_track_ttl_seconds: float = 120.0

    unknown_face_cluster_threshold: float = 0.56

    # An unknown person returning after this long counts as a new visit.
    visitor_revisit_gap_seconds: float = 600.0

    # Evidence images are written at most this often per subject / camera,
    # not once per analysed frame.
    face_crop_interval_seconds: float = 5.0
    annotated_frame_interval_seconds: float = 2.0

    # Local artifacts older than this are deleted. 0 keeps everything.
    artifact_retention_days: int = 7

    # Per-camera in-memory ring buffer of raw detections (not persisted).
    live_detection_buffer_size: int = 200

    # -----------------------------
    # Evidence capture
    # -----------------------------
    enable_event_clips: bool = True
    clip_pre_seconds: float = 4.0
    clip_post_seconds: float = 6.0

    # -----------------------------
    # Qwen model configuration
    # -----------------------------
    qwen_vl_model: str = "qwen-vl-max-latest"
    qwen_text_model: str = "qwen-max-latest"
    qwen_temporal_model: str = "qwen2.5-vl-latest"

    qwen_vl_fallback_models: str = (
        "qwen-vl-max-latest,"
        "qwen-vl-max,"
        "qwen2.5-vl-72b-instruct,"
        "qwen2.5-vl-7b-instruct"
    )

    qwen_text_fallback_models: str = (
        "qwen-max-latest,"
        "qwen-max,"
        "qwen-plus-latest,"
        "qwen-plus"
    )

    qwen_temporal_fallback_models: str = (
        "qwen2.5-vl-latest,"
        "qwen2.5-vl-72b-instruct,"
        "qwen2.5-vl-7b-instruct,"
        "qwen-vl-max-latest,"
        "qwen-vl-max"
    )

    # Enrich triggered high-risk events with multi-frame VLM analysis.
    enable_qwen_temporal: bool = True
    enable_qwen_event_analysis: bool = True
    qwen_max_images_per_temporal_call: int = 6

    # Periodic per-camera scene sanity check. Set the interval generously —
    # this is a billed cloud call per camera per interval.
    enable_qwen_scene_polling: bool = True
    qwen_scene_interval_seconds: float = 300.0

    # Cloud calls run on their own bounded executor so they can never block
    # a detection loop.
    qwen_max_concurrent: int = 2

    artifact_url_expires: int = 3600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @cached_property
    def computed_device(self) -> str:
        if self.device != "auto":
            return self.device

        return "cuda" if torch.cuda.is_available() else "cpu"

    @staticmethod
    def _split_models(value: str) -> List[str]:
        return [m.strip() for m in value.split(",") if m.strip()]

    @cached_property
    def qwen_vl_fallback_list(self) -> List[str]:
        return self._split_models(self.qwen_vl_fallback_models)

    @cached_property
    def qwen_text_fallback_list(self) -> List[str]:
        return self._split_models(self.qwen_text_fallback_models)

    @cached_property
    def qwen_temporal_fallback_list(self) -> List[str]:
        return self._split_models(self.qwen_temporal_fallback_models)


settings = Settings()