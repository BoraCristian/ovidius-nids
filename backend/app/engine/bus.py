"""Simple in-process pub/sub for live alerts and packet events.

Consumers (WebSocket, metrics, ML pipeline) subscribe via `subscribe()` and
receive a dedicated asyncio.Queue. The detection engine calls `publish()`
for every alert or traffic event."""
from __future__ import annotations

import asyncio
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self, maxsize: int = 500) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        async with self._lock:
            self._subscribers.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(q)

    async def publish(self, event: dict[str, Any]) -> None:
        # Snapshot under the lock, deliver without it so slow consumers can't block others.
        async with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop silently if a consumer is too slow — protects the engine from backpressure.
                pass


alert_bus = EventBus()     # alert events
traffic_bus = EventBus()   # raw traffic events (for live flow widget)
