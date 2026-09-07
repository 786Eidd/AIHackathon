# app/streaming/broadcaster.py

"""
Fan-out of live pipeline messages to WebSocket subscribers.

The publishers are plain OS threads (camera analyzers) and the consumers are
asyncio coroutines (WebSocket handlers), so every publish is marshalled onto
the event loop with `call_soon_threadsafe`. Nothing here may block a
publisher: subscriber queues are bounded and drop their oldest message when
full, because one operator on a slow connection must never be able to stall
weapon detection.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set

logger = logging.getLogger("nexgen.streaming.broadcaster")

# Per-subscriber backlog. Deep enough to absorb a burst of detections,
# shallow enough that a stuck client is dropped rather than buffered forever.
_SUBSCRIBER_QUEUE_SIZE = 256


class Subscriber:
    def __init__(self, camera_id: Optional[str] = None):
        self.camera_id = camera_id
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_SIZE)
        self.dropped = 0

    def wants(self, message: Dict[str, Any]) -> bool:
        if self.camera_id is None:
            return True

        # Messages without a camera_id (service-wide notices) go to everyone.
        message_camera = message.get("camera_id")

        return message_camera is None or message_camera == self.camera_id


class EventBroadcaster:
    def __init__(self):
        self._subscribers: Set[Subscriber] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Called once from the FastAPI lifespan, before any camera starts."""
        self._loop = loop

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    # -----------------------------
    # Subscription (async side)
    # -----------------------------
    def subscribe(self, camera_id: Optional[str] = None) -> Subscriber:
        subscriber = Subscriber(camera_id=camera_id)
        self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: Subscriber) -> None:
        self._subscribers.discard(subscriber)

    # -----------------------------
    # Publishing (thread side)
    # -----------------------------
    def publish(self, message: Dict[str, Any]) -> None:
        """
        Safe to call from any thread. Returns immediately.
        """
        if not self._subscribers:
            return

        loop = self._loop

        if loop is None or loop.is_closed():
            return

        try:
            loop.call_soon_threadsafe(self._fan_out, message)
        except RuntimeError:
            # Loop shut down between the check and the call.
            pass

    def _fan_out(self, message: Dict[str, Any]) -> None:
        """Runs on the event loop thread."""
        for subscriber in list(self._subscribers):
            if not subscriber.wants(message):
                continue

            try:
                subscriber.queue.put_nowait(message)
            except asyncio.QueueFull:
                # Shed the oldest message and take the newest; for live
                # monitoring, recency beats completeness.
                try:
                    subscriber.queue.get_nowait()
                    subscriber.queue.put_nowait(message)
                except Exception:
                    pass

                subscriber.dropped += 1

                if subscriber.dropped % 100 == 1:
                    logger.warning(
                        "Slow WebSocket subscriber; dropped "
                        f"{subscriber.dropped} messages."
                    )


# Single instance shared by the analyzers and the WebSocket routes.
broadcaster = EventBroadcaster()
