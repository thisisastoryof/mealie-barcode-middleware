"""Simple in-process event bus for Server-Sent Events (SSE)."""

import asyncio
import json
import threading
from typing import Any


class EventBus:
    """Fan-out pub/sub for SSE clients."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        self._loop = asyncio.get_event_loop()
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers.remove(q)

    def _dispatch(self, msg: str):
        for q in list(self._subscribers):
            q.put_nowait(msg)

    def publish(self, event: str, data: dict[str, Any]):
        msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        self._dispatch(msg)

    def publish_threadsafe(self, event: str, data: dict[str, Any]):
        """Publish from a non-async thread (e.g. APScheduler background job)."""
        msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._dispatch, msg)
        else:
            self._dispatch(msg)


scan_events = EventBus()
