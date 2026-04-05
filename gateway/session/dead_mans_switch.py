from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gateway.privacy.ram_vault import RedisRAMVault

logger = logging.getLogger(__name__)


class DeadMansSwitch:
    def __init__(self) -> None:
        self._sessions: dict[str, str] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._vaults: dict[str, "RedisRAMVault"] = {}

    async def register(
        self,
        session_id: str,
        key_id: str,
        vault: "RedisRAMVault",
        ttl: int,
    ) -> None:
        self._sessions[session_id] = key_id
        self._vaults[session_id] = vault
        self._tasks[session_id] = asyncio.create_task(
            self._countdown(session_id, ttl),
            name=f"dms-{session_id}",
        )

    async def touch(self, session_id: str) -> None:
        if session_id not in self._tasks:
            return

        vault = self._vaults.get(session_id)
        key_id = self._sessions.get(session_id)
        if not vault or not key_id:
            return

        old_task = self._tasks.pop(session_id)
        old_task.cancel()
        try:
            await old_task
        except asyncio.CancelledError:
            pass

        ttl = 300
        self._tasks[session_id] = asyncio.create_task(
            self._countdown(session_id, ttl),
            name=f"dms-{session_id}",
        )

    async def terminate(self, session_id: str) -> None:
        task = self._tasks.pop(session_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        vault = self._vaults.pop(session_id, None)
        key_id = self._sessions.pop(session_id, None)

        if vault and key_id:
            try:
                await vault.revoke(key_id)
            except Exception:
                logger.exception("Failed to revoke key %s during terminate", key_id)

    async def _expire(self, session_id: str) -> None:
        vault = self._vaults.pop(session_id, None)
        key_id = self._sessions.pop(session_id, None)
        self._tasks.pop(session_id, None)

        if vault and key_id:
            try:
                await vault.revoke(key_id)
                logger.info("Dead-man switch expired session %s — key revoked", session_id)
            except Exception:
                logger.exception("Failed to revoke key %s on expiry", key_id)

    async def _countdown(self, session_id: str, ttl: int) -> None:
        await asyncio.sleep(ttl)
        await self._expire(session_id)
