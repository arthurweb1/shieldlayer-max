import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.database.audit_log import AuditLog


@pytest.mark.asyncio
async def test_write_audit_entry_calls_execute():
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    # Create a proper async context manager
    async def async_context_manager():
        return mock_conn

    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    audit = AuditLog(pool=mock_pool)
    await audit.write(
        request_id="req-001",
        masked_prompt_hash="abc123",
        response_hash="def456",
        compliant=True,
        article_ref=None,
        watermark_seed="seed-001",
        duration_ms=123,
    )
    mock_conn.execute.assert_called_once()
    sql = mock_conn.execute.call_args[0][0]
    assert "INSERT INTO audit_events" in sql


@pytest.mark.asyncio
async def test_write_failure_propagates():
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.execute.side_effect = Exception("DB connection lost")

    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    audit = AuditLog(pool=mock_pool)
    with pytest.raises(Exception, match="DB connection lost"):
        await audit.write(
            request_id="req-002",
            masked_prompt_hash="x",
            response_hash="y",
            compliant=True,
            article_ref=None,
            watermark_seed="s",
            duration_ms=10,
        )


def test_hash_is_deterministic():
    h1 = AuditLog.hash("hello world")
    h2 = AuditLog.hash("hello world")
    assert h1 == h2
    assert len(h1) == 32  # truncated SHA256


def test_hash_different_inputs():
    assert AuditLog.hash("foo") != AuditLog.hash("bar")
