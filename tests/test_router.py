import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engine.router import HybridRouter


@pytest.fixture
def local_router():
    return HybridRouter(
        backend_type="LOCAL",
        base_url="http://localhost:9999",
        model="test-model",
        api_key="",
    )


@pytest.fixture
def cloud_router():
    return HybridRouter(
        backend_type="CLOUD",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="sk-test",
    )


@pytest.mark.asyncio
async def test_local_complete_returns_string(local_router):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Test response"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
        result = await local_router.complete("Hello")
    assert result == "Test response"


@pytest.mark.asyncio
async def test_cloud_complete_uses_api_key(cloud_router):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Cloud response"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)) as mock_post:
        result = await cloud_router.complete("Hello")

    assert result == "Cloud response"
    call_kwargs = mock_post.call_args
    headers = call_kwargs.kwargs.get("headers", {})
    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer sk-test"


@pytest.mark.asyncio
async def test_stream_yields_chunks(local_router):
    async def mock_aiter_lines():
        yield 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
        yield 'data: {"choices":[{"delta":{"content":" world"}}]}'
        yield "data: [DONE]"

    mock_response = MagicMock()
    mock_response.aiter_lines = mock_aiter_lines
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient.stream", return_value=mock_response):
        chunks = []
        async for chunk in local_router.stream("Hello"):
            chunks.append(chunk)

    assert "Hello" in chunks
    assert " world" in chunks
    assert "[DONE]" not in chunks  # sentinel filtered out


def test_invalid_backend_raises():
    with pytest.raises(ValueError, match="backend_type"):
        HybridRouter(backend_type="INVALID", base_url="http://x", model="m", api_key="")
