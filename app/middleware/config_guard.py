"""Returns HTTP 503 on all routes (except /health) when CONFIG_READY is not set."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings


class ConfigGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.config_ready and request.url.path not in {"/health", "/metrics"}:
            return JSONResponse(
                status_code=503,
                content={"detail": "Service not configured. Run the setup wizard first."},
            )
        return await call_next(request)
