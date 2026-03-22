import asyncio
import pytest
from app.engine.vault import Vault


@pytest.fixture
def vault():
    return Vault(ttl_seconds=5)  # short TTL for tests


def test_seal_and_open_roundtrip(vault):
    mapping = {"PERSON_001": "Max Mustermann", "EMAIL_001": "max@example.com"}
    session_id = vault.seal(mapping)
    recovered = vault.open(session_id)
    assert recovered == mapping


def test_open_after_purge_raises(vault):
    mapping = {"PERSON_001": "Alice"}
    session_id = vault.seal(mapping)
    vault.purge(session_id)
    with pytest.raises(KeyError):
        vault.open(session_id)


def test_two_sessions_are_independent(vault):
    sid1 = vault.seal({"PERSON_001": "Alice"})
    sid2 = vault.seal({"PERSON_001": "Bob"})
    assert vault.open(sid1)["PERSON_001"] == "Alice"
    assert vault.open(sid2)["PERSON_001"] == "Bob"


def test_empty_mapping_roundtrip(vault):
    session_id = vault.seal({})
    assert vault.open(session_id) == {}


def test_purge_nonexistent_session_is_noop(vault):
    vault.purge("nonexistent-session-id")  # must not raise


@pytest.mark.asyncio
async def test_auto_purge_after_ttl(vault):
    mapping = {"PERSON_001": "Charlie"}
    session_id = vault.seal(mapping, schedule_purge=True)
    # TTL is 5s — wait 6s
    await asyncio.sleep(6)
    with pytest.raises(KeyError):
        vault.open(session_id)
