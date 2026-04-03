"""Tests for ConfigGuardMiddleware."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.middleware.config_guard import ConfigGuardMiddleware


def _make_app(config_ready: bool) -> FastAPI:
    app = FastAPI()
    app.add_middleware(ConfigGuardMiddleware)

    @app.get("/v1/chat")
    def chat():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


def test_returns_503_when_not_configured():
    with patch("app.middleware.config_guard.get_settings") as mock:
        mock.return_value.config_ready = False
        client = TestClient(_make_app(False), raise_server_exceptions=False)
        resp = client.get("/v1/chat")
        assert resp.status_code == 503
        assert "setup wizard" in resp.json()["detail"].lower()


def test_health_bypasses_config_guard():
    with patch("app.middleware.config_guard.get_settings") as mock:
        mock.return_value.config_ready = False
        client = TestClient(_make_app(False), raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200


def test_passes_when_configured():
    with patch("app.middleware.config_guard.get_settings") as mock:
        mock.return_value.config_ready = True
        client = TestClient(_make_app(True), raise_server_exceptions=False)
        resp = client.get("/v1/chat")
        assert resp.status_code == 200
