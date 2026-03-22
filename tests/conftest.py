import pytest
from app.config import Settings


@pytest.fixture
def test_settings():
    return Settings(
        vllm_base_url="http://localhost:9999",
        postgres_dsn="postgresql://test:test@localhost:5433/test",
        audit_token="test-token",
        guardian_max_retries=3,
    )
