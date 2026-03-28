# gateway/metrics/store.py
import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket


class MetricsStore:
    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        self._subscribers: list[WebSocket] = []

    async def increment(self, key: str, amount: int = 1) -> None:
        async with self._lock:
            self._counters[key] += amount
        await self._broadcast()

    async def snapshot(self) -> dict[str, int]:
        async with self._lock:
            data = dict(self._counters)
        total = data.get("requests_total", 0)
        rewrites = data.get("compliance_rewrites", 0)
        data["compliance_score"] = (
            round(((total - rewrites) / total) * 100) if total > 0 else 100
        )
        return data

    async def subscribe(self, ws: WebSocket) -> None:
        await ws.accept()
        self._subscribers.append(ws)

    def unsubscribe(self, ws: WebSocket) -> None:
        self._subscribers = [s for s in self._subscribers if s is not ws]

    async def _broadcast(self) -> None:
        if not self._subscribers:
            return
        data = await self.snapshot()
        dead: list[WebSocket] = []
        for ws in self._subscribers:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unsubscribe(ws)
