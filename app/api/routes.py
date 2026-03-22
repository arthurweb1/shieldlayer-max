import hashlib
import io
import time as _time
import uuid
from collections import defaultdict
from typing import Optional

import re
from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.responses import Response, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from app.api.schemas import ChatRequest, ChatResponse, ComplianceInfo
from app.config import get_settings
from app.engine.guardian import ComplianceError, ComplianceResult

router = APIRouter()
security = HTTPBearer(auto_error=False)

# Simple in-memory rate limiter: 10 req/min per IP
_export_calls: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(request: Request, max_per_min: int = 10) -> None:
    ip = request.client.host if request.client else "unknown"
    now = _time.monotonic()
    calls = [t for t in _export_calls[ip] if now - t < 60]
    if len(calls) >= max_per_min:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    calls.append(now)
    _export_calls[ip] = calls


def _verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> None:
    if credentials is None or credentials.credentials != get_settings().audit_token:
        raise HTTPException(status_code=403, detail="Invalid or missing audit token")


def _get_state(request: Request):
    return request.app.state


@router.post("/v1/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest, state=Depends(_get_state)):
    start = _time.monotonic()
    request_id = str(uuid.uuid4())
    identity = getattr(request.state, "identity", None)
    caller_level = identity.level if identity else 0

    prompt_text = "\n".join(f"{m.role}: {m.content}" for m in body.messages)

    # 1. Shield: mask PII
    mask_result = state.shield.mask(prompt_text)
    masked_prompt = mask_result.masked_text

    # 2. Vault: seal PII mapping (encrypted in RAM, auto-purges after TTL)
    session_id = state.vault.seal_and_schedule(mask_result.mapping)

    # 3. Cache lookup
    cached_response = state.cache.get(masked_prompt, caller_level=caller_level)
    from_cache = cached_response is not None

    if body.stream:
        # --- Streaming path ---
        # Buffer all chunks from the router into a full response string,
        # then run the full pipeline (compliance, de-anonymize, watermark, audit)
        # on the complete text. This preserves pipeline integrity while still
        # returning a StreamingResponse to the client.
        active_router = state.router.route_for(identity) if identity else state.router
        chunks = []
        async for chunk in active_router.stream(masked_prompt):
            chunks.append(chunk)
        raw_response = "".join(chunks)

        try:
            # Compliance check on full buffered text
            try:
                compliance = await state.guardian.check(masked_prompt, raw_response)
            except ComplianceError as e:
                try:
                    await state.audit.write(
                        request_id=request_id,
                        masked_prompt_hash=hashlib.sha256(masked_prompt.encode()).hexdigest()[:32],
                        response_hash="BLOCKED",
                        compliant=False,
                        article_ref=e.article,
                        watermark_seed="N/A",
                        duration_ms=int((_time.monotonic() - start) * 1000),
                    )
                except Exception as audit_exc:
                    raise HTTPException(
                        status_code=500, detail=f"Audit write failed: {audit_exc}"
                    ) from audit_exc
                raise HTTPException(status_code=451, detail=str(e))

            # Cache compliant response
            state.cache.set(masked_prompt, raw_response, caller_level=caller_level)

            # De-anonymize using vault
            mapping = state.vault.open(session_id)
            final_response = state.shield.deanonymize(raw_response, mapping)

            # Watermark
            watermark_seed = hashlib.sha256(request_id.encode()).hexdigest()[:8]
            watermarked = state.shield.watermark(final_response, request_id=request_id)

            # Audit log
            try:
                await state.audit.write(
                    request_id=request_id,
                    masked_prompt_hash=hashlib.sha256(masked_prompt.encode()).hexdigest()[:32],
                    response_hash=hashlib.sha256(watermarked.encode()).hexdigest()[:32],
                    compliant=True,
                    article_ref=None,
                    watermark_seed=watermark_seed,
                    duration_ms=int((_time.monotonic() - start) * 1000),
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=500, detail=f"Audit write failed: {exc}"
                ) from exc
        finally:
            state.vault.purge(session_id)

        # Stream the watermarked response back to the client word-by-word
        def _sse_generator(text: str):
            words = text.split(" ")
            for i, word in enumerate(words):
                chunk = word if i == len(words) - 1 else word + " "
                yield f"data: {chunk}\n\n"

        return StreamingResponse(
            _sse_generator(watermarked),
            media_type="text/event-stream",
        )

    else:
        # --- Non-streaming path ---
        try:
            if not from_cache:
                # 4. Router call (non-streaming)
                active_router = state.router.route_for(identity) if identity else state.router
                raw_response = await active_router.complete(masked_prompt)

                # 5. Compliance check (guardian)
                try:
                    compliance = await state.guardian.check(masked_prompt, raw_response)
                except ComplianceError as e:
                    # Audit the blocked request (critical path)
                    try:
                        await state.audit.write(
                            request_id=request_id,
                            masked_prompt_hash=hashlib.sha256(masked_prompt.encode()).hexdigest()[:32],
                            response_hash="BLOCKED",
                            compliant=False,
                            article_ref=e.article,
                            watermark_seed="N/A",
                            duration_ms=int((_time.monotonic() - start) * 1000),
                        )
                    except Exception as audit_exc:
                        raise HTTPException(
                            status_code=500, detail=f"Audit write failed: {audit_exc}"
                        ) from audit_exc
                    raise HTTPException(status_code=451, detail=str(e))

                # 6. Store compliant response in cache
                state.cache.set(masked_prompt, raw_response, caller_level=caller_level)
            else:
                raw_response = cached_response
                compliance = ComplianceResult(compliant=True)

            # 7. De-anonymize using vault
            mapping = state.vault.open(session_id)
            final_response = state.shield.deanonymize(raw_response, mapping)

            # 8. Watermark
            watermark_seed = hashlib.sha256(request_id.encode()).hexdigest()[:8]
            watermarked = state.shield.watermark(final_response, request_id=request_id)

            # 9. Audit (critical path — HTTP 500 if write fails, per EU AI Act Art. 12)
            try:
                await state.audit.write(
                    request_id=request_id,
                    masked_prompt_hash=hashlib.sha256(masked_prompt.encode()).hexdigest()[:32],
                    response_hash=hashlib.sha256(watermarked.encode()).hexdigest()[:32],
                    compliant=True,
                    article_ref=None,
                    watermark_seed=watermark_seed,
                    duration_ms=int((_time.monotonic() - start) * 1000),
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=500, detail=f"Audit write failed: {exc}"
                ) from exc
        finally:
            state.vault.purge(session_id)

        retries = compliance.retries if hasattr(compliance, "retries") else 0
        return ChatResponse(
            id=request_id,
            content=watermarked,
            compliance=ComplianceInfo(compliant=True, retries=retries),
            cached=from_cache,
        )


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/audit/export")
async def audit_export(
    request: Request,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    limit: int = 1000,
    state=Depends(_get_state),
    _auth=Depends(_verify_token),
) -> Response:
    _check_rate_limit(request)
    rows = await state.audit.fetch_range(from_ts, to_ts, limit)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph("shieldlayer-max Audit Report", styles["Title"])]

    table_data = [["Request ID", "Timestamp", "Compliant", "Article", "Duration (ms)"]]
    for row in rows:
        table_data.append([
            str(row.get("request_id", ""))[:20],
            str(row.get("ts", ""))[:19],
            "YES" if row.get("compliant") else "NO",
            str(row.get("article_ref") or "—"),
            str(row.get("duration_ms", "")),
        ])

    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(t)
    doc.build(elements)
    buf.seek(0)

    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=audit_report.pdf"},
    )
