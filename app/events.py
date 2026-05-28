"""Simple in-process event bus for Server-Sent Events (SSE)."""

import asyncio
import json
from typing import Any


class EventBus:
    """Fan-out pub/sub for SSE clients."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers.remove(q)

    def publish(self, event: str, data: dict[str, Any]):
        msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        for q in list(self._subscribers):
            q.put_nowait(msg)


scan_events = EventBus()
