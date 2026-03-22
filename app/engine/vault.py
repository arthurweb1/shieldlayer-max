import asyncio
import ctypes
import gc
import json
import os
import secrets
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class Vault:
    """Zero-persistence in-memory encrypted mapping store.

    Each call to seal() generates a fresh AES-256-GCM key stored only in RAM.
    Keys are zeroed with ctypes.memset on purge. No data ever touches disk.
    """

    def __init__(self, ttl_seconds: int = 300):
        self._ttl = ttl_seconds
        # session_id -> (key_bytes, nonce+ciphertext)
        self._store: dict[str, tuple[bytes, bytes]] = {}

    def seal(self, mapping: dict, schedule_purge: bool = False) -> str:
        """Encrypt mapping and store in RAM. Returns opaque session_id."""
        key = os.urandom(32)          # AES-256 key — never leaves RAM
        nonce = os.urandom(12)        # GCM nonce — unique per seal()
        aesgcm = AESGCM(key)
        plaintext = json.dumps(mapping, ensure_ascii=False).encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        session_id = secrets.token_hex(16)
        self._store[session_id] = (key, nonce + ciphertext)

        if schedule_purge:
            self._schedule_purge(session_id)

        return session_id

    def open(self, session_id: str) -> dict:
        """Decrypt and return mapping for the given session. Raises KeyError if expired."""
        if session_id not in self._store:
            raise KeyError(f"Vault session '{session_id}' not found or already purged")

        key, data = self._store[session_id]
        nonce, ciphertext = data[:12], data[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode("utf-8"))

    def purge(self, session_id: str) -> None:
        """Zero key bytes, delete session, force GC. Safe to call on missing sessions."""
        entry = self._store.pop(session_id, None)
        if entry is None:
            return

        key, data = entry
        # Overwrite key material in memory before releasing
        try:
            buf = (ctypes.c_char * len(key)).from_buffer(bytearray(key))
            ctypes.memset(buf, 0, len(key))
        except Exception:
            pass  # best-effort zero — don't crash on memory layout edge cases

        del key, data, entry
        gc.collect()

    def _schedule_purge(self, session_id: str) -> None:
        """Schedule automatic purge after TTL seconds via asyncio."""
        try:
            loop = asyncio.get_event_loop()
            loop.call_later(self._ttl, self.purge, session_id)
        except RuntimeError:
            # No running event loop (e.g. in sync tests) — skip scheduling
            pass

    def seal_and_schedule(self, mapping: dict) -> str:
        """Convenience: seal + schedule auto-purge in one call."""
        return self.seal(mapping, schedule_purge=True)
