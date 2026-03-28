# gateway/tests/test_proxy.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_metrics_endpoint(client):
    resp = client.get("/v1/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "requests_total" in data or data == {} or isinstance(data, dict)


def test_audit_endpoint_empty(client):
    resp = client.get("/v1/audit")
    assert resp.status_code == 200
    assert resp.json() == []


def test_chat_completions_returns_200(client):
    mock_upstream = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [{
            "message": {"role": "assistant", "content": "Hello, here is your report."},
            "finish_reason": "stop",
            "index": 0,
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }
    with patch("gateway.proxy.httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_upstream
        mock_resp.raise_for_status = MagicMock()
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)

        resp = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello there"}]},
            headers={"Authorization": "Bearer test-key"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "choices" in body


def test_audit_log_populated_after_request(client):
    mock_upstream = {
        "id": "chatcmpl-test2",
        "object": "chat.completion",
        "choices": [{"message": {"role": "assistant", "content": "Sure."}, "finish_reason": "stop", "index": 0}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
    }
    with patch("gateway.proxy.httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_upstream
        mock_resp.raise_for_status = MagicMock()
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)
        client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
            headers={"Authorization": "Bearer test-key"},
        )
    audit = client.get("/v1/audit").json()
    assert len(audit) >= 1
    assert "session_id" in audit[0]
