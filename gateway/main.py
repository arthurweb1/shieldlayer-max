from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from gateway.audit.forensic import ForensicAudit
from gateway.cache.semantic_cache import SemanticCache
from gateway.config import settings
from gateway.guardian.judge import GuardianJudge
from gateway.privacy.presidio_pipeline import PrivacyPipeline
from gateway.privacy.ram_vault import RedisRAMVault
from gateway.proxy import anthropic_router, init_proxy, openai_router

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("shieldlayer")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=False)
    vault = RedisRAMVault(redis_client)

    faiss_cache = SemanticCache(
        dim=settings.faiss_dim,
        threshold=settings.semantic_cache_threshold,
        index_path=settings.faiss_index_path,
    )

    pipeline = PrivacyPipeline()
    judge = GuardianJudge()
    audit = ForensicAudit(settings.audit_log_path)

    init_proxy(pipeline, faiss_cache, judge, vault, audit)

    logger.info("ShieldLayer Max gateway online — port %d", settings.gateway_port)

    yield

    await redis_client.aclose()


app = FastAPI(
    title="ShieldLayer Max",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.monotonic()
    response: Response = await call_next(request)
    latency_ms = (time.monotonic() - start) * 1000
    response.headers["X-Gateway-Latency"] = f"{latency_ms:.2f}ms"
    return response


app.include_router(openai_router)
app.include_router(anthropic_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(
        "gateway.main:app",
        host="0.0.0.0",
        port=settings.gateway_port,
        log_level=settings.log_level.lower(),
        reload=False,
    )
