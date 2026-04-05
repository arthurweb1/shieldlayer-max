from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import AsyncGenerator

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from gateway.audit.forensic import ForensicAudit
from gateway.cache.semantic_cache import SemanticCache
from gateway.config import settings
from gateway.guardian.judge import GuardianJudge
from gateway.metrics.privacy_grade import PrivacyGradeScorer
from gateway.privacy.presidio_pipeline import PrivacyPipeline
from gateway.privacy.ram_vault import RedisRAMVault

openai_router = APIRouter(prefix="/v1")
anthropic_router = APIRouter(prefix="/anthropic")

_pipeline: PrivacyPipeline | None = None
_cache: SemanticCache | None = None
_judge: GuardianJudge | None = None
_vault: RedisRAMVault | None = None
_audit: ForensicAudit | None = None
_scorer = PrivacyGradeScorer()

_SKIP_HEADERS = {"host", "content-length", "transfer-encoding"}


def init_proxy(
    pipeline: PrivacyPipeline,
    cache: SemanticCache,
    judge: GuardianJudge,
    vault: RedisRAMVault,
    audit: ForensicAudit,
) -> None:
    global _pipeline, _cache, _judge, _vault, _audit
    _pipeline = pipeline
    _cache = cache
    _judge = judge
    _vault = vault
    _audit = audit


def _forward_headers(request: Request, session_key: bytes | None = None) -> dict[str, str]:
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _SKIP_HEADERS
    }
    if session_key:
        headers["Authorization"] = f"Bearer {session_key.decode('utf-8', errors='replace')}"
    return headers


async def _stream_response(
    upstream: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str],
    redacted_body: bytes,
    entity_map: dict[str, str],
) -> AsyncGenerator[bytes, None]:
    assert _judge is not None
    async with upstream.stream(method, url, content=redacted_body, headers=headers) as resp:
        async for chunk in resp.aiter_bytes():
            if chunk.startswith(b"data:"):
                chunk = await _judge.filter_chunk(chunk)
                if entity_map:
                    decoded = chunk.decode("utf-8", errors="replace")
                    restored = _pipeline.restore(decoded, entity_map)  # type: ignore[union-attr]
                    chunk = restored.encode("utf-8")
            yield chunk


async def process_request(
    request: Request,
    upstream_base: str,
    path: str,
) -> Response:
    assert _pipeline is not None
    assert _cache is not None
    assert _judge is not None
    assert _audit is not None

    start_ts = time.monotonic()
    session_id = request.headers.get("X-Session-Id", str(uuid.uuid4()))

    raw_body = await request.body()
    redacted_body, entity_map = _pipeline.redact_json(raw_body)

    session_key: bytes | None = None
    if _vault is not None:
        key_id = request.headers.get("X-Key-Id", session_id)
        session_key = await _vault.retrieve(key_id)

    cached = await _cache.lookup(redacted_body.decode("utf-8", errors="replace"))
    if cached is not None:
        restored = _pipeline.restore(cached, entity_map)
        latency_ms = (time.monotonic() - start_ts) * 1000

        compliance_stub = {"compliant": True, "violations": [], "risk_score": 0.0}
        grade_info = _scorer.grade(
            entities_redacted=len(entity_map),
            compliance_result=compliance_stub,
            latency_ms=latency_ms,
            cache_hit=True,
        )

        await _audit.log(
            session_id=session_id,
            redacted_body=redacted_body,
            response_body=restored.encode("utf-8"),
            entities_redacted=len(entity_map),
            compliance_result=compliance_stub,
            latency_ms=latency_ms,
        )

        return Response(
            content=restored,
            media_type="application/json",
            headers={
                "X-Cache": "HIT",
                "X-Privacy-Grade": grade_info["grade"],
                "X-Privacy-Score": str(grade_info["privacy_score"]),
            },
        )

    compliance = await _judge.evaluate(redacted_body)
    if not compliance.compliant:
        latency_ms = (time.monotonic() - start_ts) * 1000
        await _audit.log(
            session_id=session_id,
            redacted_body=redacted_body,
            response_body=b"",
            entities_redacted=len(entity_map),
            compliance_result={
                "compliant": compliance.compliant,
                "violations": compliance.violations,
                "risk_score": compliance.risk_score,
            },
            latency_ms=latency_ms,
        )
        return Response(
            content=json.dumps(
                {
                    "error": "request_blocked",
                    "reason": "EU AI Act compliance violation",
                    "violations": compliance.violations,
                    "risk_score": compliance.risk_score,
                }
            ),
            status_code=451,
            media_type="application/json",
        )

    upstream_url = f"{upstream_base.rstrip('/')}/{path}"
    forward_headers = _forward_headers(request, session_key)
    method = request.method

    is_streaming = False
    try:
        body_json = json.loads(redacted_body)
        is_streaming = body_json.get("stream", False) is True
    except (json.JSONDecodeError, AttributeError):
        pass

    client = httpx.AsyncClient(
        timeout=settings.max_proxy_timeout,
        follow_redirects=True,
    )

    if is_streaming:
        async def _gen() -> AsyncGenerator[bytes, None]:
            async with client:
                async for chunk in _stream_response(
                    client, method, upstream_url, forward_headers, redacted_body, entity_map
                ):
                    yield chunk

        return StreamingResponse(
            _gen(),
            media_type="text/event-stream",
            headers={"X-Cache": "MISS"},
        )

    async with client:
        upstream_resp = await client.request(
            method=method,
            url=upstream_url,
            content=redacted_body,
            headers=forward_headers,
        )

    response_bytes = upstream_resp.content
    response_text = response_bytes.decode("utf-8", errors="replace")
    restored_response = _pipeline.restore(response_text, entity_map)

    await _cache.store(
        redacted_body.decode("utf-8", errors="replace"),
        restored_response,
    )

    latency_ms = (time.monotonic() - start_ts) * 1000
    compliance_dict = {
        "compliant": compliance.compliant,
        "violations": compliance.violations,
        "risk_score": compliance.risk_score,
    }

    await _audit.log(
        session_id=session_id,
        redacted_body=redacted_body,
        response_body=restored_response.encode("utf-8"),
        entities_redacted=len(entity_map),
        compliance_result=compliance_dict,
        latency_ms=latency_ms,
    )

    grade_info = _scorer.grade(
        entities_redacted=len(entity_map),
        compliance_result=compliance_dict,
        latency_ms=latency_ms,
        cache_hit=False,
    )

    resp_headers = dict(upstream_resp.headers)
    resp_headers.pop("content-encoding", None)
    resp_headers.pop("transfer-encoding", None)
    resp_headers["X-Cache"] = "MISS"
    resp_headers["X-Privacy-Grade"] = grade_info["grade"]
    resp_headers["X-Privacy-Score"] = str(grade_info["privacy_score"])

    return Response(
        content=restored_response,
        status_code=upstream_resp.status_code,
        headers=resp_headers,
        media_type=upstream_resp.headers.get("content-type", "application/json"),
    )


@openai_router.post("/{path:path}")
@openai_router.get("/{path:path}")
async def openai_proxy(request: Request, path: str) -> Response:
    return await process_request(request, settings.openai_base_url, path)


@anthropic_router.post("/{path:path}")
@anthropic_router.get("/{path:path}")
async def anthropic_proxy(request: Request, path: str) -> Response:
    return await process_request(request, settings.anthropic_base_url, path)
