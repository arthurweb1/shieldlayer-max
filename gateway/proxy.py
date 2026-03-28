# gateway/proxy.py
import uuid

import httpx
from fastapi import Request

from .anonymizer.engine import AnonymizerEngine
from .anonymizer.vault import Vault
from .audit.store import AuditStore
from .compliance.judge import GuardianJudge
from .config import settings
from .metrics.store import MetricsStore
from .watermark.engine import Watermarker

_anonymizer = AnonymizerEngine()
_judge = GuardianJudge(max_rewrites=settings.guardian_max_rewrites)
_watermarker = Watermarker(secret=settings.secret_key)


def _upstream_url(model: str, path: str) -> str:
    """Route claude-* models to Anthropic; everything else to OpenAI."""
    if model.startswith("claude"):
        return f"{settings.upstream_anthropic_base}{path}"
    return f"{settings.upstream_openai_base}{path}"


async def proxy_chat_completions(request: Request, body: dict) -> dict:
    redis = request.app.state.redis
    secret_key = bytes.fromhex(settings.secret_key)
    vault = Vault(redis=redis, secret_key=secret_key, ttl=settings.vault_ttl)
    session_id = str(uuid.uuid4())
    metrics: MetricsStore = request.app.state.metrics
    audit: AuditStore = request.app.state.audit

    await metrics.increment("requests_total")

    # 1. Anonymize outbound messages
    full_mapping: dict[str, str] = {}
    pii_types: list[str] = []
    for msg in body.get("messages", []):
        if msg.get("role") in ("user", "system"):
            result = _anonymizer.anonymize(msg["content"])
            msg["content"] = result.text
            for placeholder, original in result.mapping.items():
                await vault.store(session_id, placeholder, original)
                full_mapping[placeholder] = original
                pii_types.append(placeholder.split("_")[0])

    if full_mapping:
        await metrics.increment("risks_averted", len(full_mapping))

    # 2. Forward to upstream LLM
    model = body.get("model", "")
    upstream_url = _upstream_url(model, "/chat/completions")
    auth = request.headers.get("authorization", "")
    async with httpx.AsyncClient(timeout=60.0) as client:
        upstream_resp = await client.post(
            upstream_url,
            json=body,
            headers={"Authorization": auth, "Content-Type": "application/json"},
        )
        upstream_resp.raise_for_status()
        response_body: dict = upstream_resp.json()

    # 3. De-anonymize + compliance enforce + watermark each choice
    all_violations: list[str] = []
    for choice in response_body.get("choices", []):
        content: str = choice.get("message", {}).get("content", "")
        content = _anonymizer.deanonymize(content, full_mapping)
        content, rewrite_count = await _judge.enforce(content)
        if rewrite_count > 0:
            compliance_result = _judge.check(content)
            all_violations.extend(compliance_result.violations)
            await metrics.increment("compliance_rewrites")
        content = _watermarker.apply(content, session_id=session_id)
        choice["message"]["content"] = content

    # 4. Audit log
    await audit.append(
        session_id=session_id,
        pii_types=list(set(pii_types)),
        violations=all_violations,
        watermarked=True,
    )

    await vault.flush(session_id)
    return response_body
