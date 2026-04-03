from dataclasses import dataclass
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

VALID_ROLES = {"viewer": 0, "analyst": 1, "admin": 2}
EXEMPT_PATHS = {"/health", "/metrics"}


@dataclass
class RequestIdentity:
    org_id: str
    role: str
    level: int


class RBACMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        org_id = request.headers.get("X-Org-ID", "").strip()
        role = request.headers.get("X-User-Role", "").strip().lower()

        if not org_id or role not in VALID_ROLES:
            return JSONResponse(
                status_code=403,
                content={"detail": "Missing or invalid X-Org-ID / X-User-Role headers"},
            )

        request.state.identity = RequestIdentity(
            org_id=org_id,
            role=role,
            level=VALID_ROLES[role],
        )
        return await call_next(request)
