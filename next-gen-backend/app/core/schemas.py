# app/core/schemas.py

from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Anything OpenCV/FFmpeg can demux is fair game, but rejecting obvious typos
# here beats a camera that sits in "error" state forever.
_ALLOWED_STREAM_SCHEMES = (
    "rtsp://",
    "rtsps://",
    "http://",
    "https://",
    "rtmp://",
)


def _validate_stream_url(value: str) -> str:
    value = value.strip()

    if not value.lower().startswith(_ALLOWED_STREAM_SCHEMES):
        raise ValueError(
            "rtsp_url must start with one of: "
            + ", ".join(_ALLOWED_STREAM_SCHEMES)
        )

    return value


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    rtsp_url: str = Field(min_length=1, max_length=1024)
    location: Optional[str] = None
    enabled: bool = True
    sample_fps: Optional[float] = Field(default=None, gt=0, le=30)

    @field_validator("rtsp_url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return _validate_stream_url(value)


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    rtsp_url: Optional[str] = Field(default=None, min_length=1, max_length=1024)
    location: Optional[str] = None
    enabled: Optional[bool] = None
    sample_fps: Optional[float] = Field(default=None, gt=0, le=30)

    @field_validator("rtsp_url")
    @classmethod
    def _check_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        return _validate_stream_url(value)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)

    # Omit camera_id to ask across every camera.
    camera_id: Optional[str] = None

    # How far back to pull events/alerts for context.
    minutes: int = Field(default=60, ge=1, le=10080)
