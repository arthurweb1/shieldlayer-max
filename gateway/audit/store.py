# gateway/audit/store.py
import asyncio
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class AuditEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    session_id: str = ""
    pii_types: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    watermarked: bool = False


class AuditStore:
    def __init__(self, max_entries: int = 10_000) -> None:
        self._entries: list[AuditEntry] = []
        self._lock = asyncio.Lock()
        self._max = max_entries

    async def append(
        self,
        session_id: str,
        pii_types: list[str],
        violations: list[str],
        watermarked: bool,
    ) -> None:
        entry = AuditEntry(
            session_id=session_id,
            pii_types=pii_types,
            violations=violations,
            watermarked=watermarked,
        )
        async with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max:
                self._entries = self._entries[-self._max :]

    async def all(self) -> list[dict]:
        async with self._lock:
            return [asdict(e) for e in reversed(self._entries)]
