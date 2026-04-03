# gateway/anonymizer/vault.py
import json

import redis.asyncio as aioredis

from .crypto import encrypt, decrypt


class Vault:
    """In-memory Redis vault with AES-256-GCM encrypted PII mappings and TTL."""

    def __init__(self, redis: aioredis.Redis, secret_key: bytes, ttl: int = 300) -> None:
        self._r = redis
        self._key = secret_key
        self._ttl = ttl

    def _redis_key(self, session_id: str) -> str:
        return f"shieldlayer:vault:{session_id}"

    async def store(self, session_id: str, placeholder: str, original: str) -> None:
        """Encrypt and store placeholder->original mapping under session_id."""
        rkey = self._redis_key(session_id)
        raw = await self._r.get(rkey)
        mapping: dict[str, str] = json.loads(raw) if raw else {}
        mapping[placeholder] = encrypt(self._key, original).hex()
        await self._r.set(rkey, json.dumps(mapping), ex=self._ttl)

    async def retrieve(self, session_id: str, placeholder: str) -> str | None:
        """Decrypt and return the original value for placeholder, or None on miss."""
        rkey = self._redis_key(session_id)
        raw = await self._r.get(rkey)
        if not raw:
            return None
        mapping: dict[str, str] = json.loads(raw)
        blob_hex = mapping.get(placeholder)
        if not blob_hex:
            return None
        return decrypt(self._key, bytes.fromhex(blob_hex))

    async def flush(self, session_id: str) -> None:
        """Delete the entire vault entry for session_id."""
        await self._r.delete(self._redis_key(session_id))
