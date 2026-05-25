"""Per-project event bus for SSE pipeline progress."""
from __future__ import annotations
import asyncio
from collections import defaultdict
from typing import AsyncIterator

class EventBus:
    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, project_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues[project_id].append(q)
        return q

    def unsubscribe(self, project_id: str, q: asyncio.Queue) -> None:
        if q in self._queues[project_id]:
            self._queues[project_id].remove(q)

    async def publish(self, project_id: str, event: dict) -> None:
        for q in list(self._queues.get(project_id, [])):
            try:
                q.put_nowait(event)
            except Exception:
                pass

    async def stream(self, project_id: str) -> AsyncIterator[dict]:
        q = self.subscribe(project_id)
        try:
            while True:
                ev = await q.get()
                yield ev
                if ev.get("type") in ("done", "error"):
                    break
        finally:
            self.unsubscribe(project_id, q)

events = EventBus()
