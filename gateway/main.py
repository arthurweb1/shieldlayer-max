# gateway/main.py
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .audit.store import AuditStore
from .config import settings
from .metrics.store import MetricsStore
from .router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    app.state.metrics = MetricsStore()
    app.state.audit = AuditStore()
    yield
    await app.state.redis.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="ShieldLayer Max Gateway", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
