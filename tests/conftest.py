import pytest
from app.config import Settings, get_settings


@pytest.fixture
def test_settings():
    # Override only the fields needed for isolation. Fields not overridden
    # (vllm_model, shield_synonym_pairs_path, etc.) retain production defaults.
    return Settings(
        vllm_base_url="http://localhost:9999",
        postgres_dsn="postgresql://test:test@localhost:5433/test",
        audit_token="test-token",
        guardian_max_retries=3,
    )


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the lru_cache before each test to ensure clean Settings state."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
