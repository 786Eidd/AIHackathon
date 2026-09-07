# app/db/models.py

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Camera(Base):
    """
    A registered live camera stream.

    `status` is maintained by the StreamManager and reflects the live
    connection, while `enabled` is operator intent: an enabled camera is
    started automatically on service boot and restarted after connection
    loss. The two are deliberately separate so a camera that is simply
    unreachable does not get silently un-enrolled.
    """

    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    name: Mapped[str] = mapped_column(String(255))

    # Credentials are embedded in the URL (rtsp://user:pass@host/path).
    rtsp_url: Mapped[str] = mapped_column(String(1024))

    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # offline | connecting | online | error
    status: Mapped[str] = mapped_column(String(32), default="offline")

    last_error: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    last_frame_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Per-camera override of settings.stream_sample_fps.
    sample_fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class Event(Base):
    """
    A security event on a live stream.

    Rows are created the moment a track opens, so operators are alerted
    without waiting for the subject to leave frame, and then finalized
    (ended_at / detection_count / clip_key) when the track closes.

    Raw per-frame detections are intentionally not stored here — they live in
    a bounded in-memory ring buffer per camera. At N cameras a row per
    detection would be a constant write stream.
    """

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), index=True)

    event_type: Mapped[str] = mapped_column(String(128), index=True)

    # info | low | medium | high
    risk_level: Mapped[str] = mapped_column(String(16), index=True)

    # open | closed
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    detection_count: Mapped[int] = mapped_column(Integer, default=1)

    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    snapshot_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    clip_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class Alert(Base):
    """
    An operator-facing alert derived from an Event.

    `message` starts as a deterministic template so the alert can be pushed
    immediately, and is upgraded in place if the VLM enrichment call returns.
    """

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    camera_id: Mapped[str] = mapped_column(String(64), index=True)

    # HIGH | MEDIUM | LOW
    priority: Mapped[str] = mapped_column(String(16), index=True)

    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)

    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
