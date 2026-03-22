from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.config import get_settings
from app.api.routes import router as api_router
from app.engine.shield import ShieldEngine
from app.engine.guardian import GuardianEngine
from app.engine.vault import Vault
from app.engine.router import HybridRouter
from app.database.vector_cache import VectorCache
from app.database.audit_log import AuditLog


def create_app(
    shield=None,
    guardian=None,
    cache=None,
    audit=None,
    router=None,
    vault=None,
) -> FastAPI:
    """Factory — accepts injected components for testing."""
    _shield = shield
    _guardian = guardian
    _cache = cache
    _audit = audit
    _router = router
    _vault = vault

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal _shield, _guardian, _cache, _audit, _router, _vault
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
        if _vault is None:
            _vault = Vault(ttl_seconds=settings.vault_session_ttl_seconds)
        if _router is None:
            base_url = (
                settings.vllm_base_url
                if settings.llm_backend_type == "LOCAL"
                else settings.openai_base_url
            )
            _router = HybridRouter(
                backend_type=settings.llm_backend_type,
                base_url=base_url,
                model=settings.vllm_model,
                api_key=settings.openai_api_key,
            )

        app.state.shield = _shield
        app.state.guardian = _guardian
        app.state.cache = _cache
        app.state.audit = _audit
        app.state.vault = _vault
        app.state.router = _router

        yield

    app = FastAPI(title="shieldlayer-max", lifespan=lifespan)

    # Pre-populate state for test injection: when all components are provided,
    # set them directly so they are available even if the lifespan event is not
    # triggered (e.g., when using httpx ASGITransport in tests).
    if all(x is not None for x in [_shield, _guardian, _cache, _audit, _vault, _router]):
        app.state.shield = _shield
        app.state.guardian = _guardian
        app.state.cache = _cache
        app.state.audit = _audit
        app.state.vault = _vault
        app.state.router = _router

    app.include_router(api_router)

    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
