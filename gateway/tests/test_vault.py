# gateway/tests/test_vault.py
import pytest
from gateway.anonymizer.crypto import encrypt, decrypt


def test_encrypt_decrypt_roundtrip():
    key = b"\x00" * 32
    plaintext = "PERSON_001=John Doe"
    ciphertext = encrypt(key, plaintext)
    assert ciphertext != plaintext.encode()
    assert decrypt(key, ciphertext) == plaintext


def test_different_ciphertexts_same_plaintext():
    key = b"\x01" * 32
    ct1 = encrypt(key, "hello")
    ct2 = encrypt(key, "hello")
    assert ct1 != ct2  # random nonce per call


# --- Vault tests (appended in Task A3) ---
import json
from unittest.mock import AsyncMock
from gateway.anonymizer.vault import Vault


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.set = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.delete = AsyncMock()
    return r


@pytest.mark.asyncio
async def test_vault_store_calls_redis_set(mock_redis):
    key = b"\x02" * 32
    vault = Vault(redis=mock_redis, secret_key=key, ttl=300)
    await vault.store("sess-1", "PERSON_001", "Alice Smith")
    assert mock_redis.set.called


@pytest.mark.asyncio
async def test_vault_retrieve_returns_none_on_miss(mock_redis):
    key = b"\x02" * 32
    vault = Vault(redis=mock_redis, secret_key=key, ttl=300)
    result = await vault.retrieve("sess-999", "PERSON_001")
    assert result is None


@pytest.mark.asyncio
async def test_vault_store_then_retrieve_roundtrip():
    """Integration test using a fake in-memory Redis store."""
    _store: dict[str, str] = {}

    fake_redis = AsyncMock()

    async def fake_set(k, v, ex=None):
        _store[k] = v

    async def fake_get(k):
        return _store.get(k)

    async def fake_delete(k):
        _store.pop(k, None)

    fake_redis.set = fake_set
    fake_redis.get = fake_get
    fake_redis.delete = fake_delete

    key = b"\x03" * 32
    vault = Vault(redis=fake_redis, secret_key=key, ttl=300)
    await vault.store("sess-rt", "EMAIL_001", "alice@example.com")
    result = await vault.retrieve("sess-rt", "EMAIL_001")
    assert result == "alice@example.com"


@pytest.mark.asyncio
async def test_vault_flush_deletes_key():
    _store: dict[str, str] = {}

    fake_redis = AsyncMock()

    async def fake_set(k, v, ex=None):
        _store[k] = v

    async def fake_get(k):
        return _store.get(k)

    async def fake_delete(k):
        _store.pop(k, None)

    fake_redis.set = fake_set
    fake_redis.get = fake_get
    fake_redis.delete = fake_delete

    key = b"\x04" * 32
    vault = Vault(redis=fake_redis, secret_key=key, ttl=300)
    await vault.store("sess-flush", "PERSON_001", "Bob")
    await vault.flush("sess-flush")
    result = await vault.retrieve("sess-flush", "PERSON_001")
    assert result is None
