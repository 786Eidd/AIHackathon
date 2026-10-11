# app/core/timeutil.py

import re
from datetime import datetime
from typing import Optional


def iso_utc(value: Optional[datetime]) -> Optional[str]:
    """
    Timestamps are stored as naive UTC. Without an explicit zone marker a
    browser parses them as local time, so every API/WebSocket payload goes
    through here.
    """
    if value is None:
        return None

    return value.replace(tzinfo=None).isoformat() + "Z"


_CREDENTIALS = re.compile(r"://[^/@\s]+@")


def redact_url(url: str) -> str:
    """Strips user:pass from a stream URL before it is logged or broadcast."""
    return _CREDENTIALS.sub("://***@", url or "")
