import pytest
from unittest.mock import AsyncMock, MagicMock
from starlette.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import FastAPI
from app.middleware.auth import RBACMiddleware, RequestIdentity

def _make_app():
    app = FastAPI()
    app.add_middleware(RBACMiddleware)

    @app.get("/v1/chat")
    async def chat(request: Request):
        identity = request.state.identity
        return {"org": identity.org_id, "role": identity.role, "level": identity.level}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


def test_missing_headers_returns_403():
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/v1/chat")
    assert resp.status_code == 403


def test_invalid_role_returns_403():
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/v1/chat", headers={"X-Org-ID": "rd", "X-User-Role": "superuser"})
    assert resp.status_code == 403


def test_valid_headers_attach_identity():
    client = TestClient(_make_app())
    resp = client.get("/v1/chat", headers={"X-Org-ID": "rd", "X-User-Role": "analyst"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["org"] == "rd"
    assert data["role"] == "analyst"
    assert data["level"] == 1


def test_health_exempt_from_auth():
    client = TestClient(_make_app())
    resp = client.get("/health")
    assert resp.status_code == 200


def test_metrics_exempt_from_auth():
    app = _make_app()

    @app.get("/metrics")
    async def metrics():
        return "metrics"

    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200


def test_admin_role_level():
    client = TestClient(_make_app())
    resp = client.get("/v1/chat", headers={"X-Org-ID": "admin", "X-User-Role": "admin"})
    assert resp.json()["level"] == 2


def test_viewer_role_level():
    client = TestClient(_make_app())
    resp = client.get("/v1/chat", headers={"X-Org-ID": "legal", "X-User-Role": "viewer"})
    assert resp.json()["level"] == 0
