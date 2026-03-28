# gateway/tests/test_audit.py
import pytest
from gateway.audit.store import AuditStore


@pytest.mark.asyncio
async def test_append_and_retrieve():
    store = AuditStore()
    await store.append("sess-1", ["PERSON", "EMAIL"], [], True)
    entries = await store.all()
    assert len(entries) == 1
    assert entries[0]["session_id"] == "sess-1"
    assert "PERSON" in entries[0]["pii_types"]
    assert entries[0]["watermarked"] is True


@pytest.mark.asyncio
async def test_most_recent_first():
    store = AuditStore()
    await store.append("sess-a", [], [], False)
    await store.append("sess-b", [], [], False)
    entries = await store.all()
    assert entries[0]["session_id"] == "sess-b"
    assert entries[1]["session_id"] == "sess-a"


@pytest.mark.asyncio
async def test_max_entries_cap():
    store = AuditStore(max_entries=3)
    for i in range(5):
        await store.append(f"sess-{i}", [], [], False)
    entries = await store.all()
    assert len(entries) == 3


@pytest.mark.asyncio
async def test_entry_has_required_fields():
    store = AuditStore()
    await store.append("sess-x", ["PHONE"], ["[Art.12] violation"], False)
    entry = (await store.all())[0]
    assert "id" in entry
    assert "timestamp" in entry
    assert "session_id" in entry
    assert "pii_types" in entry
    assert "violations" in entry
    assert "watermarked" in entry
    assert entry["violations"] == ["[Art.12] violation"]


@pytest.mark.asyncio
async def test_empty_store_returns_empty_list():
    store = AuditStore()
    assert await store.all() == []
