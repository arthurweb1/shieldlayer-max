# gateway/tests/conftest.py
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

os.environ.setdefault("GATEWAY_TEST_MODE", "1")

from gateway.main import create_app
from gateway.metrics.store import MetricsStore
from gateway.audit.store import AuditStore


@pytest.fixture
def client():
    app = create_app()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.aclose = AsyncMock()
    app.state.metrics = MetricsStore()
    app.state.audit = AuditStore()
    with patch("gateway.main.aioredis.from_url", return_value=mock_redis):
        with TestClient(app) as c:
            yield c
