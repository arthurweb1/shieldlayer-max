from contextlib import asynccontextmanager
from typing import Callable, Awaitable, Optional

import httpx
from fastapi import FastAPI

from app.config import get_settings
from app.api.routes import router
from app.engine.shield import ShieldEngine
from app.engine.guardian import GuardianEngine
from app.database.vector_cache import VectorCache
from app.database.audit_log import AuditLog


async def _default_vllm_call(prompt: str) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{settings.vllm_base_url}/v1/chat/completions",
            json={
                "model": settings.vllm_model,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def create_app(
    shield=None,
    guardian=None,
    cache=None,
    audit=None,
    vllm_call=None,
) -> FastAPI:
    """Factory — accepts injected components for testing."""
    _shield = shield
    _guardian = guardian
    _cache = cache
    _audit = audit
    _vllm_call = vllm_call or _default_vllm_call

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal _shield, _guardian, _cache, _audit
        settings = get_settings()
        if _shield is None:
            _shield = ShieldEngine()
        if _guardian is None:
            _guardian = GuardianEngine(
                base_url=settings.vllm_base_url,
                model=settings.vllm_guardian_model,
                max_retries=settings.guardian_max_retries,
            )
        if _cache is None:
            _cache = VectorCache(threshold=settings.cache_similarity_threshold)
        if _audit is None:
            _audit = await AuditLog.create(settings.postgres_dsn)

        app.state.shield = _shield
        app.state.guardian = _guardian
        app.state.cache = _cache
        app.state.audit = _audit
        app.state.vllm_call = _vllm_call

        yield

    app = FastAPI(title="shieldlayer-max", lifespan=lifespan)

    # Pre-populate state for test injection: when all components are provided,
    # set them directly so they are available even if the lifespan event is not
    # triggered (e.g., when using httpx ASGITransport in tests).
    if all(x is not None for x in [_shield, _guardian, _cache, _audit]):
        app.state.shield = _shield
        app.state.guardian = _guardian
        app.state.cache = _cache
        app.state.audit = _audit
        app.state.vllm_call = _vllm_call
    app.include_router(router)
    return app


app = create_app()
