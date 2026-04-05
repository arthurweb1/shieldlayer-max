from __future__ import annotations

import ctypes

import redis.asyncio as aioredis


class RedisRAMVault:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def store(self, key_id: str, secret: bytes, ttl: int) -> None:
        await self._redis.set(key_id, secret, ex=ttl)
        self._zero_memory(secret)

    async def retrieve(self, key_id: str) -> bytes | None:
        value = await self._redis.get(key_id)
        return value if isinstance(value, bytes) else None

    async def revoke(self, key_id: str) -> None:
        await self._redis.delete(key_id)

    async def rotate(self, key_id: str, new_secret: bytes, ttl: int) -> None:
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.delete(key_id)
            pipe.set(key_id, new_secret, ex=ttl)
            await pipe.execute()
        self._zero_memory(new_secret)

    def _zero_memory(self, data: bytes) -> None:
        """
        Best-effort zeroing of a bytes object in CPython memory.

        CPython's memory model does not guarantee that zeroing the underlying
        buffer of an immutable bytes object prevents the data from persisting
        elsewhere (e.g. interned strings, copy-on-write pages). For stricter
        zeroing semantics, use bytearray — see _zero_bytearray below.
        """
        try:
            ctypes.memmove(ctypes.c_char_p(id(data)), b"\x00" * len(data), len(data))
        except Exception:
            pass

    def _zero_bytearray(self, data: bytearray) -> None:
        for i in range(len(data)):
            data[i] = 0
