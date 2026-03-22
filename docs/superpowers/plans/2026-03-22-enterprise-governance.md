# Enterprise Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add RBAC middleware, per-org LLM policy routing, cache ACL, a guided setup wizard, and an analytics dashboard to shieldlayer-max.

**Architecture:** Three independent subsystems (B → A → C). Subsystem B adds department identity headers and secures the cache and LLM routing. Subsystem A adds a CLI/web setup wizard that runs on first boot. Subsystem C extends the audit schema and adds a Streamlit analytics dashboard.

**Tech Stack:** FastAPI BaseHTTPMiddleware, questionary, Streamlit, Plotly, asyncpg JSONB codec, FAISS parallel metadata arrays

**Spec:** `docs/superpowers/specs/2026-03-22-enterprise-governance-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `app/middleware/__init__.py` | Create | Package marker |
| `app/middleware/auth.py` | Create | `RequestIdentity` dataclass + `RBACMiddleware` |
| `app/engine/router.py` | Modify | Add `local_config`/`cloud_config` + `route_for(identity)` |
| `app/database/vector_cache.py` | Modify | Add `caller_level` ACL to `get()`/`set()` |
| `app/database/audit_log.py` | Modify | Add `pii_stats`+`cached` columns, JSONB codec, RO user |
| `app/engine/shield.py` | Modify | Add `pii_stats: dict` to `MaskResult` |
| `app/api/routes.py` | Modify | Identity-aware routing, cache ACL, pii_stats in audit |
| `app/main.py` | Modify | Register middleware, dual-config router, `config_ready` guard |
| `app/config.py` | Modify | New fields: `config_ready`, `compliance_strictness`, `postgres_ro_password`, `cloud_price_per_1k_tokens` |
| `app/setup_wizard.py` | Create | CLI wizard using questionary |
| `entrypoint.sh` | Create | Docker entrypoint — runs wizard if no .env |
| `dashboard/__init__.py` | Create | Package marker |
| `dashboard/setup.py` | Create | Streamlit setup UI |
| `dashboard/main.py` | Create | Analytics dashboard (cost, compliance, privacy) |
| `Dockerfile.dashboard` | Create | Streamlit container |
| `requirements-dashboard.txt` | Create | Streamlit-only deps |
| `docker-compose.yml` | Modify | Dual networks, entrypoint, dashboard service |
| `tests/test_auth.py` | Create | RBAC middleware unit tests |
| `tests/test_vector_cache.py` | Modify | Add ACL tests |
| `tests/test_routes.py` | Modify | Add identity header tests |
| `tests/test_shield.py` | Modify | Add `pii_stats` assertion |

---

## Task 1: RBAC Middleware

**Files:**
- Create: `app/middleware/__init__.py`
- Create: `app/middleware/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_auth.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from starlette.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import FastAPI
from app.middleware.auth import RBACMiddleware, RequestIdentity

def _make_app():
    app = FastAPI()
    app.add_middleware(RBACMiddleware)

    @app.get("/v1/chat")
    async def chat(request: Request):
        identity = request.state.identity
        return {"org": identity.org_id, "role": identity.role, "level": identity.level}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


def test_missing_headers_returns_403():
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/v1/chat")
    assert resp.status_code == 403


def test_invalid_role_returns_403():
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/v1/chat", headers={"X-Org-ID": "rd", "X-User-Role": "superuser"})
    assert resp.status_code == 403


def test_valid_headers_attach_identity():
    client = TestClient(_make_app())
    resp = client.get("/v1/chat", headers={"X-Org-ID": "rd", "X-User-Role": "analyst"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["org"] == "rd"
    assert data["role"] == "analyst"
    assert data["level"] == 1


def test_health_exempt_from_auth():
    client = TestClient(_make_app())
    resp = client.get("/health")
    assert resp.status_code == 200


def test_metrics_exempt_from_auth():
    app = _make_app()

    @app.get("/metrics")
    async def metrics():
        return "metrics"

    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200


def test_admin_role_level():
    client = TestClient(_make_app())
    resp = client.get("/v1/chat", headers={"X-Org-ID": "admin", "X-User-Role": "admin"})
    assert resp.json()["level"] == 2


def test_viewer_role_level():
    client = TestClient(_make_app())
    resp = client.get("/v1/chat", headers={"X-Org-ID": "legal", "X-User-Role": "viewer"})
    assert resp.json()["level"] == 0
```

- [ ] **Step 2: Run — verify FAIL**

```bash
cd /c/Users/gigus/OneDrive/Dokumente/GitHub/shieldlayer-max/.worktrees/implement
py -3.11 -m pytest tests/test_auth.py -v
```
Expected: `ImportError` — module not found

- [ ] **Step 3: Create `app/middleware/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Implement `app/middleware/auth.py`**

```python
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
```

- [ ] **Step 5: Run — verify PASS**

```bash
py -3.11 -m pytest tests/test_auth.py -v
```
Expected: 7 PASS

- [ ] **Step 6: Commit**

```bash
git add app/middleware/__init__.py app/middleware/auth.py tests/test_auth.py
git commit -m "feat: RBAC middleware — RequestIdentity from X-Org-ID / X-User-Role headers"
```

---

## Task 2: Cache ACL

**Files:**
- Modify: `app/database/vector_cache.py`
- Modify: `tests/test_vector_cache.py`

- [ ] **Step 1: Add failing ACL tests to `tests/test_vector_cache.py`**

Append these to the existing test file:

```python
# --- ACL tests ---

def test_cache_acl_admin_sees_admin_entry():
    """Admin (level 2) can see admin-level cached entries."""
    cache = VectorCache(threshold=0.97)
    cache.set("What is the EU AI Act?", "EU AI Act explanation.", caller_level=2)
    result = cache.get("What is the EU AI Act?", caller_level=2)
    assert result == "EU AI Act explanation."


def test_cache_acl_viewer_cannot_see_admin_entry():
    """Viewer (level 0) cannot see an admin-level (level 2) cached entry."""
    cache = VectorCache(threshold=0.97)
    cache.set("What is the EU AI Act?", "EU AI Act explanation.", caller_level=2)
    result = cache.get("What is the EU AI Act?", caller_level=0)
    assert result is None


def test_cache_acl_admin_can_see_viewer_entry():
    """Admin (level 2) can see a viewer-level (level 0) cached entry."""
    cache = VectorCache(threshold=0.97)
    cache.set("What is the EU AI Act?", "EU AI Act explanation.", caller_level=0)
    result = cache.get("What is the EU AI Act?", caller_level=2)
    assert result == "EU AI Act explanation."


def test_cache_acl_backward_compatible():
    """Callers without caller_level default to 0 (viewer) — no breaking change."""
    cache = VectorCache(threshold=0.97)
    cache.set("Simple question", "Simple answer.")
    result = cache.get("Simple question")
    assert result == "Simple answer."
```

- [ ] **Step 2: Run — verify FAIL**

```bash
py -3.11 -m pytest tests/test_vector_cache.py::test_cache_acl_viewer_cannot_see_admin_entry -v
```
Expected: FAIL — `set()` does not accept `caller_level`

- [ ] **Step 3: Update `app/database/vector_cache.py`**

```python
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from threading import Lock


class VectorCache:
    def __init__(self, threshold: float = 0.97, model_name: str = "all-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)
        self._threshold = threshold
        self._index = faiss.IndexFlatIP(384)  # Inner product on L2-normalized = cosine similarity
        self._values: list[str] = []
        self._levels: list[int] = []   # parallel to _values — permission level of creator
        self._lock = Lock()

    def _encode(self, text: str) -> np.ndarray:
        vec = self._model.encode([text], normalize_embeddings=True)
        return vec.astype("float32")

    def get(self, query: str, caller_level: int = 0) -> str | None:
        """Return cached value if similarity >= threshold AND stored_level <= caller_level."""
        with self._lock:
            if self._index.ntotal == 0:
                return None
            vec = self._encode(query)
            distances, indices = self._index.search(vec, 1)
            score = float(distances[0][0])
            if score >= self._threshold:
                idx = int(indices[0][0])
                stored_level = self._levels[idx]
                if stored_level <= caller_level:
                    return self._values[idx]
            return None

    def set(self, query: str, value: str, caller_level: int = 0) -> None:
        """Store a cached entry tagged with the caller's permission level."""
        with self._lock:
            vec = self._encode(query)
            self._index.add(vec)
            self._values.append(value)
            self._levels.append(caller_level)
```

- [ ] **Step 4: Run all cache tests — verify PASS**

```bash
py -3.11 -m pytest tests/test_vector_cache.py -v
```
Expected: All PASS (including existing tests — backward-compatible)

- [ ] **Step 5: Commit**

```bash
git add app/database/vector_cache.py tests/test_vector_cache.py
git commit -m "feat: cache ACL — caller_level prevents cross-department cache leakage"
```

---

## Task 3: Policy Routing — HybridRouter + dual-config

**Files:**
- Modify: `app/engine/router.py`
- Modify: `tests/test_router.py`

- [ ] **Step 1: Add failing tests to `tests/test_router.py`**

Append to the existing test file:

```python
# --- Policy routing tests ---
from app.middleware.auth import RequestIdentity

def test_route_for_admin_org_returns_cloud_router(test_settings):
    """Admin org gets CLOUD backend when backend_type=CLOUD."""
    router = HybridRouter(
        backend_type="LOCAL",
        base_url="http://local:8000",
        model="local-model",
        api_key="",
        local_config={"base_url": "http://local:8000", "model": "local-model"},
        cloud_config={"base_url": "https://api.openai.com/v1", "model": "gpt-4o", "api_key": "sk-test"},
    )
    identity = RequestIdentity(org_id="admin", role="admin", level=2)
    routed = router.route_for(identity)
    # Admin org uses CLOUD config when cloud_config is provided
    assert routed._base_url == "https://api.openai.com/v1"
    assert routed._api_key == "sk-test"


def test_route_for_non_admin_org_always_local():
    """Non-admin org is always routed to LOCAL regardless of backend_type."""
    router = HybridRouter(
        backend_type="CLOUD",
        base_url="https://api.openai.com/v1",
        model="gpt-4o",
        api_key="sk-test",
        local_config={"base_url": "http://vllm:8000", "model": "llama"},
        cloud_config={"base_url": "https://api.openai.com/v1", "model": "gpt-4o", "api_key": "sk-test"},
    )
    identity = RequestIdentity(org_id="rd", role="analyst", level=1)
    routed = router.route_for(identity)
    assert routed._base_url == "http://vllm:8000"
    assert routed._backend == "LOCAL"


def test_route_for_without_dual_config_falls_back_to_self():
    """If no dual config provided, route_for returns a clone of self."""
    router = HybridRouter(
        backend_type="LOCAL", base_url="http://vllm:8000", model="llama", api_key=""
    )
    identity = RequestIdentity(org_id="rd", role="analyst", level=1)
    routed = router.route_for(identity)
    assert routed._base_url == "http://vllm:8000"
```

- [ ] **Step 2: Run — verify FAIL**

```bash
py -3.11 -m pytest tests/test_router.py -k "route_for" -v
```
Expected: FAIL — `HybridRouter.__init__` does not accept `local_config`/`cloud_config`

- [ ] **Step 3: Update `app/engine/router.py`**

```python
import json
from typing import AsyncGenerator, Optional

import httpx

VALID_BACKENDS = {"LOCAL", "CLOUD"}


class HybridRouter:
    """Routes LLM calls to LOCAL (vLLM) or CLOUD (OpenAI-compatible) backend.

    The masked prompt is sent to whichever backend is configured.
    PII has already been stripped by ShieldEngine before reaching the router.

    When constructed with local_config + cloud_config, route_for(identity)
    selects the appropriate backend per org policy.
    """

    def __init__(
        self,
        backend_type: str,
        base_url: str,
        model: str,
        api_key: str,
        local_config: Optional[dict] = None,
        cloud_config: Optional[dict] = None,
    ):
        if backend_type not in VALID_BACKENDS:
            raise ValueError(f"backend_type must be one of {VALID_BACKENDS}, got '{backend_type}'")
        self._backend = backend_type
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._local_config = local_config
        self._cloud_config = cloud_config

    def route_for(self, identity) -> "HybridRouter":
        """Return a single-backend HybridRouter scoped to the org's allowed backend.

        Admin org: uses cloud_config if available, otherwise falls back to local.
        All other orgs: always LOCAL regardless of global backend_type.
        Falls back to a clone of self when no dual config is available.
        """
        if identity.org_id == "admin" and self._cloud_config:
            cfg = self._cloud_config
            return HybridRouter(
                backend_type="CLOUD",
                base_url=cfg["base_url"],
                model=cfg["model"],
                api_key=cfg.get("api_key", ""),
            )
        if self._local_config:
            cfg = self._local_config
            return HybridRouter(
                backend_type="LOCAL",
                base_url=cfg["base_url"],
                model=cfg["model"],
                api_key="",
            )
        # No dual config — return a clone of self (backward-compatible)
        return HybridRouter(
            backend_type=self._backend,
            base_url=self._base_url,
            model=self._model,
            api_key=self._api_key,
        )

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _payload(self, prompt: str, stream: bool = False) -> dict:
        return {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }

    async def complete(self, prompt: str) -> str:
        """Non-streaming completion. Returns full response text."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(prompt, stream=False),
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Streaming completion. Yields text tokens as they arrive."""
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(prompt, stream=True),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
```

- [ ] **Step 4: Run all router tests — verify PASS**

```bash
py -3.11 -m pytest tests/test_router.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add app/engine/router.py tests/test_router.py
git commit -m "feat: HybridRouter dual-config + route_for(identity) org policy routing"
```

---

## Task 4: Wire RBAC into routes.py + main.py

**Files:**
- Modify: `app/api/routes.py`
- Modify: `app/main.py`
- Modify: `tests/test_routes.py`

- [ ] **Step 1: Add failing tests to `tests/test_routes.py`**

Append to the existing test file:

```python
# --- RBAC / identity header tests ---
from app.middleware.auth import RequestIdentity

def _make_identity(org_id="rd", role="analyst", level=1):
    return RequestIdentity(org_id=org_id, role=role, level=level)


@pytest.mark.asyncio
async def test_chat_uses_route_for_identity():
    """routes.py must call state.router.route_for(identity) not state.router directly."""
    from app.main import create_app
    from app.engine.shield import ShieldEngine, MaskResult
    from app.engine.guardian import GuardianEngine, ComplianceResult
    from app.database.vector_cache import VectorCache
    from app.database.audit_log import AuditLog
    from app.engine.router import HybridRouter
    from app.engine.vault import Vault

    mock_shield = MagicMock(spec=ShieldEngine)
    mock_shield.mask.return_value = MaskResult(
        masked_text="PERSON_001 asks about regulations.",
        mapping={"PERSON_001": "Alice"},
        pii_stats={"PERSON": 1},
    )
    mock_shield.deanonymize.return_value = "Alice asks about regulations."
    mock_shield.watermark.return_value = "Alice asks about regulations."

    mock_guardian = AsyncMock(spec=GuardianEngine)
    mock_guardian.check.return_value = ComplianceResult(compliant=True)
    mock_cache = MagicMock(spec=VectorCache)
    mock_cache.get.return_value = None
    mock_audit = AsyncMock(spec=AuditLog)
    mock_vault = MagicMock(spec=Vault)
    mock_vault.seal_and_schedule.return_value = "sid-001"
    mock_vault.open.return_value = {"PERSON_001": "Alice"}

    # mock_router.route_for returns a sub-router with .complete
    mock_sub_router = AsyncMock()
    mock_sub_router.complete = AsyncMock(return_value="Regulation response.")
    mock_router = MagicMock(spec=HybridRouter)
    mock_router.route_for.return_value = mock_sub_router

    app = create_app(
        shield=mock_shield, guardian=mock_guardian, cache=mock_cache,
        audit=mock_audit, router=mock_router, vault=mock_vault,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat",
            json={"messages": [{"role": "user", "content": "Alice asks about regulations."}]},
            headers={"X-Org-ID": "rd", "X-User-Role": "analyst"},
        )
    assert resp.status_code == 200
    mock_router.route_for.assert_called_once()


@pytest.mark.asyncio
async def test_chat_without_identity_headers_returns_403():
    """Missing identity headers → 403 (middleware rejects before handler runs)."""
    from app.main import create_app
    from app.engine.shield import ShieldEngine
    from app.engine.guardian import GuardianEngine
    from app.database.vector_cache import VectorCache
    from app.database.audit_log import AuditLog
    from app.engine.router import HybridRouter
    from app.engine.vault import Vault

    app = create_app(
        shield=MagicMock(spec=ShieldEngine),
        guardian=AsyncMock(spec=GuardianEngine),
        cache=MagicMock(spec=VectorCache),
        audit=AsyncMock(spec=AuditLog),
        router=MagicMock(spec=HybridRouter),
        vault=MagicMock(spec=Vault),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 403
```

- [ ] **Step 2: Run — verify FAIL**

```bash
py -3.11 -m pytest tests/test_routes.py::test_chat_without_identity_headers_returns_403 -v
```
Expected: FAIL — middleware not registered

- [ ] **Step 3: Update `app/api/routes.py`**

In the `chat` handler:
1. Add `request: Request` to the function signature (FastAPI auto-injects)
2. Read identity: `identity = getattr(request.state, "identity", None)`
3. Replace `state.router.complete(masked_prompt)` with `state.router.route_for(identity).complete(masked_prompt)`
4. Replace the streaming path `state.router.stream(...)` with `state.router.route_for(identity).stream(...)`
5. Pass `caller_level=identity.level if identity else 0` to `state.cache.get()` and `state.cache.set()`

Full updated `chat` function signature and key call sites (rest of function unchanged):

```python
@router.post("/v1/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest, state=Depends(_get_state)) -> ChatResponse:
    start = _time.monotonic()
    request_id = str(uuid.uuid4())
    identity = getattr(request.state, "identity", None)
    caller_level = identity.level if identity else 0

    prompt_text = "\n".join(f"{m.role}: {m.content}" for m in body.messages)

    # 1. Shield: mask PII
    mask_result = state.shield.mask(prompt_text)
    masked_prompt = mask_result.masked_text

    # 2. Vault: encrypt mapping
    session_id = state.vault.seal_and_schedule(mask_result.mapping)

    # 3. Cache lookup (ACL-aware)
    cached_response = state.cache.get(masked_prompt, caller_level=caller_level)
    from_cache = cached_response is not None

    try:
        if not from_cache:
            # 4. LLM call via policy-routed router
            active_router = state.router.route_for(identity) if identity else state.router
            if body.stream:
                chunks = []
                async for chunk in active_router.stream(masked_prompt):
                    chunks.append(chunk)
                raw_response = "".join(chunks)
            else:
                raw_response = await active_router.complete(masked_prompt)

            # 5. Compliance check
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
                        pii_stats=mask_result.pii_stats,
                        cached=False,
                    )
                except Exception as audit_exc:
                    raise HTTPException(status_code=500, detail=f"Audit write failed: {audit_exc}") from audit_exc
                raise HTTPException(status_code=451, detail=str(e))

            # 6. Store in cache (ACL-aware)
            state.cache.set(masked_prompt, raw_response, caller_level=caller_level)
        else:
            raw_response = cached_response
            compliance = ComplianceResult(compliant=True)

        # 7. De-anonymize via vault
        mapping = state.vault.open(session_id)
        final_response = state.shield.deanonymize(raw_response, mapping)

        # 8. Watermark
        watermark_seed = hashlib.sha256(request_id.encode()).hexdigest()[:8]
        watermarked = state.shield.watermark(final_response, request_id=request_id)

        # 9. Audit (critical path)
        try:
            await state.audit.write(
                request_id=request_id,
                masked_prompt_hash=hashlib.sha256(masked_prompt.encode()).hexdigest()[:32],
                response_hash=hashlib.sha256(watermarked.encode()).hexdigest()[:32],
                compliant=True,
                article_ref=None,
                watermark_seed=watermark_seed,
                duration_ms=int((_time.monotonic() - start) * 1000),
                pii_stats=mask_result.pii_stats,
                cached=from_cache,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Audit write failed: {exc}") from exc

    finally:
        state.vault.purge(session_id)

    retries = compliance.retries if hasattr(compliance, "retries") else 0
    return ChatResponse(
        id=request_id,
        content=watermarked,
        compliance=ComplianceInfo(compliant=True, retries=retries),
        cached=from_cache,
    )
```

Also add the `ComplianceResult` import at the top (it's already there — no change needed).

- [ ] **Step 4: Update `app/main.py`**

Changes:
1. Import `RBACMiddleware` from `app.middleware.auth`
2. Import `HybridRouter` is already imported
3. Register middleware: `app.add_middleware(RBACMiddleware)` before `app.include_router(api_router)`
4. Update dual-config router construction in lifespan and pre-population block:

```python
# In lifespan, replace existing router construction:
if _router is None:
    _router = HybridRouter(
        backend_type=settings.llm_backend_type,
        base_url=settings.vllm_base_url if settings.llm_backend_type == "LOCAL" else settings.openai_base_url,
        model=settings.vllm_model,
        api_key=settings.openai_api_key,
        local_config={"base_url": settings.vllm_base_url, "model": settings.vllm_model},
        cloud_config={
            "base_url": settings.openai_base_url,
            "model": settings.vllm_model,
            "api_key": settings.openai_api_key,
        },
    )
```

5. In `create_app()`, add middleware registration:

```python
app.add_middleware(RBACMiddleware)
```

- [ ] **Step 5: Note on existing tests** — the two new tests added in this task should pass now. The 6 existing tests in `test_routes.py` that mock `MaskResult` will fail after Task 5 adds the `pii_stats` field (because `MaskResult(masked_text=..., mapping=...)` will be missing the required field). **Do not fix them yet** — Task 5, Step 4 fixes all 6 `MaskResult(...)` calls in `test_routes.py` explicitly. If the existing tests unexpectedly fail after this task's changes (before Task 5), that is expected and not a blocker.

- [ ] **Step 6: Run new tests — verify PASS**

```bash
py -3.11 -m pytest tests/test_routes.py::test_chat_without_identity_headers_returns_403 tests/test_routes.py::test_chat_uses_route_for_identity -v
```
Expected: PASS (existing tests may fail due to missing `pii_stats` — fixed in Task 5)

- [ ] **Step 7: Commit**

```bash
git add app/api/routes.py app/main.py tests/test_routes.py
git commit -m "feat: wire RBAC middleware, identity-aware routing and cache ACL into pipeline"
```

---

## Task 5: MaskResult.pii_stats + Audit Schema Extensions

**Files:**
- Modify: `app/engine/shield.py`
- Modify: `app/database/audit_log.py`
- Modify: `tests/test_shield.py`
- Modify: `tests/test_audit_log.py`

- [ ] **Step 1: Add failing shield test**

Add to `tests/test_shield.py`:

```python
def test_mask_returns_pii_stats(shield):
    text = "Max Mustermann at max@example.com wants help."
    result = shield.mask(text)
    assert isinstance(result.pii_stats, dict)
    # At minimum one entity type should be detected
    assert sum(result.pii_stats.values()) >= 1


def test_mask_no_pii_returns_empty_stats(shield):
    text = "The weather is nice today."
    result = shield.mask(text)
    assert result.pii_stats == {}
```

- [ ] **Step 2: Run — verify FAIL**

```bash
py -3.11 -m pytest tests/test_shield.py::test_mask_returns_pii_stats -v
```
Expected: FAIL — `MaskResult` has no `pii_stats`

- [ ] **Step 3: Update `app/engine/shield.py` — add `pii_stats` to `MaskResult`**

Change the dataclass:

```python
@dataclass
class MaskResult:
    masked_text: str
    mapping: dict  # pseudonym → original (reverse map for de-anonymization)
    pii_stats: dict  # entity_type → count e.g. {"PERSON": 2, "EMAIL_ADDRESS": 1}
```

In `mask()`, add stats building before the return:

```python
# Build pii_stats from counters (already populated in the loop)
pii_stats = dict(counters)  # counters maps entity_type → count

return MaskResult(masked_text=masked, mapping=reverse, pii_stats=pii_stats)
```

Also update the early-return when no PII found:

```python
if not pii_results:
    return MaskResult(masked_text=text, mapping={}, pii_stats={})
```

- [ ] **Step 4: Fix all existing `MaskResult(...)` calls in tests**

In `tests/test_routes.py`, update all `MaskResult(masked_text=..., mapping=...)` calls to include `pii_stats={}`:

```python
mock_shield.mask.return_value = MaskResult(
    masked_text="PERSON_001 wants to know about regulations.",
    mapping={"PERSON_001": "Max Mustermann"},
    pii_stats={"PERSON": 1},
)
```

Apply to all 6 `MaskResult(...)` instances in `tests/test_routes.py`.

- [ ] **Step 5: Run shield tests — verify PASS**

```bash
py -3.11 -m pytest tests/test_shield.py -v
```
Expected: All PASS

- [ ] **Step 6: Update `app/database/audit_log.py`** — schema extensions + JSONB codec + RO user + new `write()` params

```python
import hashlib
import json
from typing import Optional

import asyncpg

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_id TEXT NOT NULL,
    masked_prompt_hash TEXT NOT NULL,
    response_hash TEXT NOT NULL,
    compliant BOOLEAN NOT NULL,
    article_ref TEXT,
    watermark_seed TEXT NOT NULL,
    duration_ms INTEGER NOT NULL
);
"""

MIGRATE_SQL = """
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS pii_stats JSONB DEFAULT '{}';
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS cached BOOLEAN NOT NULL DEFAULT false;
"""

INSERT_SQL = """
INSERT INTO audit_events
    (request_id, masked_prompt_hash, response_hash, compliant, article_ref,
     watermark_seed, duration_ms, pii_stats, cached)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
"""


async def _init_conn(conn: asyncpg.Connection) -> None:
    """Register JSONB codec so pii_stats is returned as dict, not raw string."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


class AuditLog:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    @classmethod
    async def create(cls, dsn: str, ro_password: str = "readonly") -> "AuditLog":
        pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10, init=_init_conn)
        async with pool.acquire() as conn:
            await conn.execute(CREATE_TABLE_SQL)
            await conn.execute(MIGRATE_SQL)
            # Create read-only user for the dashboard (idempotent via DO block)
            await conn.execute(f"""
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='shieldlayer_ro') THEN
    CREATE ROLE shieldlayer_ro LOGIN PASSWORD '{ro_password}';
    GRANT CONNECT ON DATABASE shieldlayer TO shieldlayer_ro;
    GRANT USAGE ON SCHEMA public TO shieldlayer_ro;
    GRANT SELECT ON audit_events TO shieldlayer_ro;
  END IF;
END $$;
""")
        return cls(pool=pool)

    async def write(
        self,
        *,
        request_id: str,
        masked_prompt_hash: str,
        response_hash: str,
        compliant: bool,
        article_ref: Optional[str],
        watermark_seed: str,
        duration_ms: int,
        pii_stats: Optional[dict] = None,
        cached: bool = False,
    ) -> None:
        """Write audit entry. Raises on failure — critical path (EU AI Act Art. 12)."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                INSERT_SQL,
                request_id,
                masked_prompt_hash,
                response_hash,
                compliant,
                article_ref,
                watermark_seed,
                duration_ms,
                pii_stats or {},
                cached,
            )

    @staticmethod
    def hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    async def fetch_range(
        self,
        from_ts: Optional[str],
        to_ts: Optional[str],
        limit: int,
    ) -> list[dict]:
        query = "SELECT * FROM audit_events WHERE 1=1"
        params: list = []
        if from_ts:
            params.append(from_ts)
            query += f" AND ts >= ${len(params)}::timestamptz"
        if to_ts:
            params.append(to_ts)
            query += f" AND ts <= ${len(params)}::timestamptz"
        query += f" ORDER BY ts DESC LIMIT {limit}"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]
```

- [ ] **Step 7: Update `app/main.py`** — pass `ro_password` to `AuditLog.create()`

In the lifespan:
```python
if _audit is None:
    _audit = await AuditLog.create(settings.postgres_dsn, ro_password=settings.postgres_ro_password)
```

- [ ] **Step 8: Update audit_log test** — add `pii_stats` and `cached` to `write()` call in `tests/test_audit_log.py`

```python
# In test_write_audit_entry: add pii_stats and cached kwargs
await audit.write(
    request_id="req-001",
    masked_prompt_hash="abc123",
    response_hash="def456",
    compliant=True,
    article_ref=None,
    watermark_seed="seed-001",
    duration_ms=123,
    pii_stats={"PERSON": 1},
    cached=False,
)
# call_args[0] is the positional args tuple: (SQL, req_id, hash, hash, compliant, article, seed, dur, pii_stats, cached)
# Indices: 0=SQL, 1=request_id, 2=masked_prompt_hash, 3=response_hash,
#          4=compliant, 5=article_ref, 6=watermark_seed, 7=duration_ms,
#          8=pii_stats, 9=cached
call_args = mock_conn.execute.call_args[0]
assert "INSERT INTO audit_events" in call_args[0]
assert call_args[8] == {"PERSON": 1}   # pii_stats (9th positional arg, index 8)
assert call_args[9] is False            # cached (10th positional arg, index 9)
```

- [ ] **Step 9: Run full test suite — verify all PASS**

```bash
py -3.11 -m pytest tests/ -v --tb=short
```
Expected: All PASS

- [ ] **Step 10: Commit**

```bash
git add app/engine/shield.py app/database/audit_log.py app/main.py tests/test_shield.py tests/test_audit_log.py tests/test_routes.py
git commit -m "feat: MaskResult.pii_stats, audit schema pii_stats+cached, JSONB codec, RO user"
```

---

## Task 6: Config Fields + Setup Wizard + CONFIG_READY Guard

**Files:**
- Modify: `app/config.py`
- Create: `app/setup_wizard.py`
- Modify: `app/main.py`
- Create: `entrypoint.sh`
- Modify: `requirements.txt`

- [ ] **Step 1: Update `app/config.py`**

Add new fields:

```python
# In Settings class, add:
config_ready: bool = False
compliance_strictness: str = "MEDIUM"   # LOW | MEDIUM | HIGH
postgres_ro_password: str = "readonly"
cloud_price_per_1k_tokens: float = 0.002
```

- [ ] **Step 2: Add `questionary==2.0.1` to `requirements.txt`**

Append to `requirements.txt`:
```
questionary==2.0.1
```

- [ ] **Step 3: Create `app/setup_wizard.py`**

```python
#!/usr/bin/env python3
"""Interactive CLI setup wizard. Runs when .env does not exist."""
import os
import secrets
import shutil
import subprocess
from pathlib import Path

try:
    import questionary
except ImportError:
    print("questionary not installed. Run: pip install questionary")
    raise


ENV_FILE = Path(".env")
ENV_TMP = Path(".env.tmp")


def _detect_gpu() -> bool:
    try:
        result = subprocess.run(
            ["nvidia-smi"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _generate_password() -> str:
    return secrets.token_hex(16)


def _write_env(values: dict) -> None:
    lines = [f"{k}={v}" for k, v in values.items()]
    ENV_TMP.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_TMP.rename(ENV_FILE)


def run_wizard() -> None:
    print("\n=== shieldlayer-max Setup Wizard ===\n")

    # 1. GPU detection
    has_gpu = _detect_gpu()
    if has_gpu:
        use_vllm = questionary.confirm(
            "NVIDIA GPU detected. Use vLLM for high-performance local inference?",
            default=True,
        ).ask()
        llm_backend = "LOCAL"  # vLLM always uses LOCAL backend type
        vllm_base_url = "http://vllm:8000" if use_vllm else "http://host.docker.internal:11434"
        vllm_model = questionary.text(
            "vLLM model name:", default="meta-llama/Meta-Llama-3-8B-Instruct"
        ).ask()
    else:
        print("No NVIDIA GPU detected. Using CPU inference via Ollama.")
        llm_backend = "LOCAL"
        vllm_base_url = questionary.text(
            "Ollama base URL:", default="http://host.docker.internal:11434"
        ).ask()
        vllm_model = questionary.text("Model name:", default="mistral").ask()

    # 2. Backend mode
    mode = questionary.select(
        "Deployment mode:",
        choices=["Local-only (Air-Gapped)", "Hybrid-Cloud (OpenAI-compatible)"],
    ).ask()
    openai_api_key = ""
    if "Hybrid" in mode:
        llm_backend = "CLOUD"
        openai_api_key = questionary.password("OpenAI API key:").ask() or ""

    # 3. Compliance strictness
    strictness = questionary.select(
        "Compliance strictness:",
        choices=[
            "LOW — Log only, no blocking",
            "MEDIUM — Standard filter (recommended)",
            "HIGH — Paranoid: block on any suspicion",
        ],
        default="MEDIUM — Standard filter (recommended)",
    ).ask()
    strictness_key = strictness.split(" — ")[0]  # "LOW", "MEDIUM", or "HIGH"
    guardian_retries = {"LOW": 2, "MEDIUM": 2, "HIGH": 0}[strictness_key]

    # 4. Security
    vault_key = secrets.token_hex(32)
    print(f"\nAuto-generated VAULT_ENCRYPTION_KEY: {vault_key[:8]}...{vault_key[-8:]}")

    audit_token = ""
    while not audit_token or audit_token.lower() in ("change-me", ""):
        audit_token = questionary.password(
            "Set AUDIT_TOKEN (used to export PDF audit log):"
        ).ask() or ""
        if not audit_token or audit_token.lower() == "change-me":
            print("  Error: AUDIT_TOKEN cannot be empty or 'change-me'. Please set a strong value.")

    # 5. Postgres password
    default_pg_pw = _generate_password()
    pg_password = questionary.password(
        f"PostgreSQL password (leave blank for auto-generated):",
    ).ask() or default_pg_pw
    pg_password = pg_password or default_pg_pw

    ro_password = _generate_password()

    # 6. Write .env
    values = {
        "VLLM_BASE_URL": vllm_base_url,
        "VLLM_MODEL": vllm_model,
        "VLLM_GUARDIAN_MODEL": vllm_model,
        "LLM_BACKEND_TYPE": llm_backend,
        "OPENAI_API_KEY": openai_api_key,
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
        "POSTGRES_USER": "shieldlayer",
        "POSTGRES_PASSWORD": pg_password,
        "POSTGRES_DB": "shieldlayer",
        "POSTGRES_DSN": f"postgresql://shieldlayer:{pg_password}@postgres:5432/shieldlayer",
        "POSTGRES_RO_PASSWORD": ro_password,
        "VAULT_SESSION_TTL_SECONDS": "300",
        "VAULT_ENCRYPTION_KEY": vault_key,
        "AUDIT_TOKEN": audit_token,
        "GUARDIAN_MAX_RETRIES": str(guardian_retries),
        "COMPLIANCE_STRICTNESS": strictness_key,
        "CACHE_SIMILARITY_THRESHOLD": "0.97",
        "SHIELD_SYNONYM_PAIRS_PATH": "/app/data/synonym_pairs.json",
        "CLOUD_PRICE_PER_1K_TOKENS": "0.002",
        "CONFIG_READY": "true",
    }
    _write_env(values)

    print("\n✓ .env written successfully.")
    print(f"  Backend:    {llm_backend} ({vllm_model})")
    print(f"  Strictness: {strictness_key}")
    print(f"  Audit token: {audit_token[:4]}****")
    print("\nRun: docker compose up -d\n")


if __name__ == "__main__":
    if ENV_FILE.exists():
        print(".env already exists. Delete it to re-run the wizard.")
    else:
        run_wizard()
```

- [ ] **Step 4: Update `app/main.py` — add `config_ready` guard**

In the `lifespan` handler, add at the very top of the `async with` block:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    nonlocal _shield, _guardian, _cache, _audit, _router, _vault
    settings = get_settings()

    # CONFIG_READY guard — if setup wizard hasn't run yet, serve 503 on all routes
    if not settings.config_ready:
        app.state.config_ready = False
        yield
        return

    app.state.config_ready = True
    # ... rest of existing init code ...
```

Also add a 503 middleware at the app level that checks `config_ready`:

```python
@app.middleware("http")
async def setup_guard(request: Request, call_next):
    if not getattr(app.state, "config_ready", True):
        if request.url.path == "/health":
            return await call_next(request)
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"detail": "Setup required. Visit http://localhost:8501"},
        )
    return await call_next(request)
```

- [ ] **Step 5: Create `entrypoint.sh`**

```sh
#!/bin/sh
set -e
if [ ! -f /app/.env ]; then
    echo "No .env found — running setup wizard..."
    python app/setup_wizard.py
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Make it executable in the Dockerfile (add `RUN chmod +x /app/entrypoint.sh` and `ENTRYPOINT ["/app/entrypoint.sh"]` — update in Task 8).

- [ ] **Step 6: Run full test suite to verify no regressions**

```bash
py -3.11 -m pytest tests/ -v --tb=short
```
Expected: All existing tests still PASS (setup_wizard is not tested here — it requires interactive TTY)

- [ ] **Step 7: Commit**

```bash
git add app/config.py app/setup_wizard.py app/main.py entrypoint.sh requirements.txt
git commit -m "feat: setup wizard, CONFIG_READY guard, compliance strictness config"
```

---

## Task 7: Analytics Dashboard

**Files:**
- Create: `dashboard/__init__.py`
- Create: `dashboard/setup.py`
- Create: `dashboard/main.py`
- Create: `requirements-dashboard.txt`
- Create: `Dockerfile.dashboard`

- [ ] **Step 1: Create `requirements-dashboard.txt`**

```
streamlit==1.35.0
plotly==5.22.0
streamlit-autorefresh==1.0.1
asyncpg==0.29.0
```

- [ ] **Step 2: Create `Dockerfile.dashboard`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements-dashboard.txt .
RUN pip install --no-cache-dir -r requirements-dashboard.txt

COPY dashboard/ ./dashboard/
COPY data/ ./data/

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

- [ ] **Step 3: Create `dashboard/__init__.py`**

Empty file.

- [ ] **Step 4: Create `dashboard/setup.py`** — Streamlit setup UI (standalone Streamlit app, run separately via `streamlit run dashboard/setup.py`; not integrated with `main.py`)

```python
"""Streamlit setup wizard UI — browser-based alternative to the CLI wizard."""
import os
import secrets
import streamlit as st
from pathlib import Path

ENV_FILE = Path("/app/.env")

st.set_page_config(page_title="shieldlayer-max Setup", page_icon="🛡️")
st.title("shieldlayer-max Setup Wizard")
st.markdown("Configure your deployment. Fields marked **required** cannot be left blank.")

with st.form("setup_form"):
    st.subheader("LLM Backend")
    backend = st.selectbox("Backend Type", ["LOCAL (vLLM / Ollama)", "CLOUD (OpenAI-compatible)"])
    vllm_url = st.text_input("LLM Base URL", value="http://vllm:8000")
    vllm_model = st.text_input("Model Name", value="meta-llama/Meta-Llama-3-8B-Instruct")
    openai_key = st.text_input("OpenAI API Key (CLOUD only)", type="password", value="")

    st.subheader("Compliance")
    strictness = st.select_slider(
        "Strictness Level",
        options=["LOW", "MEDIUM", "HIGH"],
        value="MEDIUM",
    )

    st.subheader("Security")
    audit_token = st.text_input("AUDIT_TOKEN **required**", type="password")
    pg_password = st.text_input(
        "PostgreSQL Password (leave blank to auto-generate)", type="password"
    )

    submitted = st.form_submit_button("Write .env and Start")

if submitted:
    if not audit_token or audit_token.lower() == "change-me":
        st.error("AUDIT_TOKEN cannot be empty or 'change-me'.")
    else:
        pg_pw = pg_password or secrets.token_hex(16)
        ro_pw = secrets.token_hex(16)
        vault_key = secrets.token_hex(32)
        backend_type = "CLOUD" if "CLOUD" in backend else "LOCAL"
        guardian_retries = {"LOW": 2, "MEDIUM": 2, "HIGH": 0}[strictness]

        lines = [
            f"VLLM_BASE_URL={vllm_url}",
            f"VLLM_MODEL={vllm_model}",
            f"VLLM_GUARDIAN_MODEL={vllm_model}",
            f"LLM_BACKEND_TYPE={backend_type}",
            f"OPENAI_API_KEY={openai_key}",
            "OPENAI_BASE_URL=https://api.openai.com/v1",
            "POSTGRES_USER=shieldlayer",
            f"POSTGRES_PASSWORD={pg_pw}",
            "POSTGRES_DB=shieldlayer",
            f"POSTGRES_DSN=postgresql://shieldlayer:{pg_pw}@postgres:5432/shieldlayer",
            f"POSTGRES_RO_PASSWORD={ro_pw}",
            "VAULT_SESSION_TTL_SECONDS=300",
            f"VAULT_ENCRYPTION_KEY={vault_key}",
            f"AUDIT_TOKEN={audit_token}",
            f"GUARDIAN_MAX_RETRIES={guardian_retries}",
            f"COMPLIANCE_STRICTNESS={strictness}",
            "CACHE_SIMILARITY_THRESHOLD=0.97",
            "SHIELD_SYNONYM_PAIRS_PATH=/app/data/synonym_pairs.json",
            "CLOUD_PRICE_PER_1K_TOKENS=0.002",
            "CONFIG_READY=true",
        ]
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        st.success(".env written successfully! Restart the app container to apply.")
        st.code("docker compose restart app")
```

- [ ] **Step 5: Create `dashboard/main.py`** — analytics dashboard

```python
"""Guardian Analytics Dashboard — C-level view over the audit log."""
import os
import asyncio
import json
from datetime import datetime

import asyncpg
import plotly.graph_objects as go
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=30_000, key="autorefresh")
except ImportError:
    pass

st.set_page_config(page_title="ShieldLayer Analytics", layout="wide")
st.title("ShieldLayer Max — Governance Dashboard")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# --- DB connection ---
POSTGRES_DSN = os.getenv(
    "POSTGRES_RO_DSN",
    "postgresql://shieldlayer_ro:{pw}@postgres:5432/shieldlayer".format(
        pw=os.getenv("POSTGRES_RO_PASSWORD", "readonly")
    ),
)
PRICE_PER_1K = float(os.getenv("CLOUD_PRICE_PER_1K_TOKENS", "0.002"))
AVG_TOKENS = 500


@st.cache_data(ttl=30)
def fetch_all() -> dict:
    async def _run():
        conn = await asyncpg.connect(POSTGRES_DSN)
        await conn.set_type_codec(
            "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
        )
        try:
            cache_hits = await conn.fetchval(
                "SELECT COUNT(*) FROM audit_events WHERE cached=true AND ts >= NOW() - INTERVAL '1 day'"
            )
            total_blocked = await conn.fetchval(
                "SELECT COUNT(*) FROM audit_events WHERE article_ref IS NOT NULL"
            )
            article_rows = await conn.fetch(
                """SELECT article_ref, COUNT(*) as cnt
                   FROM audit_events
                   WHERE article_ref IS NOT NULL AND ts >= NOW() - INTERVAL '30 days'
                   GROUP BY article_ref"""
            )
            daily_rows = await conn.fetch(
                """SELECT DATE(ts) as day,
                          COUNT(*) FILTER (WHERE article_ref IS NOT NULL) as blocked,
                          COUNT(*) FILTER (WHERE article_ref IS NULL) as compliant
                   FROM audit_events
                   WHERE ts >= NOW() - INTERVAL '30 days'
                   GROUP BY day ORDER BY day"""
            )
            pii_rows = await conn.fetch(
                "SELECT pii_stats FROM audit_events WHERE ts >= NOW() - INTERVAL '7 days'"
            )
        finally:
            await conn.close()
        return {
            "cache_hits": cache_hits or 0,
            "total_blocked": total_blocked or 0,
            "article_rows": [dict(r) for r in article_rows],
            "daily_rows": [dict(r) for r in daily_rows],
            "pii_rows": [r["pii_stats"] for r in pii_rows],
        }

    return asyncio.run(_run())


try:
    data = fetch_all()
except Exception as exc:
    st.error(f"Cannot connect to database: {exc}")
    st.info("Make sure POSTGRES_RO_DSN or POSTGRES_RO_PASSWORD is set correctly.")
    st.stop()

col1, col2, col3 = st.columns(3)

# --- Panel 1: Cost-Savings Tracker ---
with col1:
    st.subheader("Cost-Savings Tracker")
    hits = data["cache_hits"]
    saved = hits * AVG_TOKENS * (PRICE_PER_1K / 1000)
    st.metric("Cache Hits Today", hits)
    st.metric("Estimated Cloud Cost Saved", f"${saved:.4f}")
    st.caption(f"Based on {AVG_TOKENS} avg tokens × ${PRICE_PER_1K}/1K tokens")

# --- Panel 2: Compliance Heatmap ---
with col2:
    st.subheader("EU AI Act Compliance")
    articles = ["Art. 5", "Art. 10", "Art. 12", "Art. 13"]
    article_counts = {row["article_ref"]: row["cnt"] for row in data["article_rows"]}
    values = [article_counts.get(a, 0) for a in articles]

    fig_radar = go.Figure(go.Scatterpolar(
        r=values + [values[0]],
        theta=articles + [articles[0]],
        fill="toself",
        name="Violations",
        line_color="crimson",
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True)),
        showlegend=False,
        margin=dict(l=20, r=20, t=30, b=20),
        height=300,
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    if data["daily_rows"]:
        days = [str(r["day"]) for r in data["daily_rows"]]
        blocked = [r["blocked"] for r in data["daily_rows"]]
        compliant = [r["compliant"] for r in data["daily_rows"]]
        fig_bar = go.Figure([
            go.Bar(name="Blocked (451)", x=days, y=blocked, marker_color="crimson"),
            go.Bar(name="Compliant", x=days, y=compliant, marker_color="steelblue"),
        ])
        fig_bar.update_layout(barmode="stack", height=200, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_bar, use_container_width=True)

# --- Panel 3: Privacy Metrics ---
with col3:
    st.subheader("Privacy Metrics (7 days)")
    aggregated: dict[str, int] = {}
    for stats in data["pii_rows"]:
        if isinstance(stats, dict):
            for entity, count in stats.items():
                aggregated[entity] = aggregated.get(entity, 0) + count

    if aggregated:
        sorted_entities = sorted(aggregated.items(), key=lambda x: x[1], reverse=True)
        labels, counts = zip(*sorted_entities)
        fig_pii = go.Figure(go.Bar(x=list(labels), y=list(counts), marker_color="darkorange"))
        fig_pii.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_pii, use_container_width=True)
        st.metric("Total PII Entities Masked (7d)", sum(counts))
    else:
        st.info("No PII data yet.")
```

- [ ] **Step 6: Commit**

```bash
git add dashboard/ requirements-dashboard.txt Dockerfile.dashboard
git commit -m "feat: analytics dashboard — cost savings, compliance heatmap, PII metrics"
```

---

## Task 8: Docker Compose — Networks + Entrypoint + Dashboard Service

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Read the current `docker-compose.yml`**

```bash
cat docker-compose.yml
```

- [ ] **Step 2: Update `docker-compose.yml`**

Full replacement content:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: shieldlayer
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-CHANGE_ME}
      POSTGRES_DB: shieldlayer
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U shieldlayer"]
      interval: 5s
      retries: 5
    networks:
      - frontend_net

  vllm:
    image: vllm/vllm-openai:latest
    command: ["--model", "${VLLM_MODEL}", "--served-model-name", "${VLLM_MODEL}"]
    volumes:
      - ${HF_HOME:-~/.cache/huggingface}:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 10s
      retries: 10
    networks:
      - inference_net

  app:
    build: .
    env_file: .env
    entrypoint: ["/app/entrypoint.sh"]
    ports:
      - "8080:8000"
    depends_on:
      postgres:
        condition: service_healthy
      vllm:
        condition: service_healthy
    networks:
      - frontend_net
      - inference_net

  dashboard:
    build:
      context: .
      dockerfile: Dockerfile.dashboard
    env_file: .env
    ports:
      - "8501:8501"
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - frontend_net

volumes:
  pgdata:

networks:
  frontend_net:
    driver: bridge
  inference_net:
    driver: bridge
    internal: true
```

- [ ] **Step 3: Update `Dockerfile`** — add entrypoint and make it executable

The current `Dockerfile` ends with:
```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Replace that last line and add the entrypoint copy:
```dockerfile
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
```
Remove the `CMD [...]` line — `entrypoint.sh` calls `exec uvicorn ...` directly.

- [ ] **Step 4: Run final test suite**

```bash
py -3.11 -m pytest tests/ -v --tb=short
```
Expected: All tests PASS

- [ ] **Step 5: Final commit**

```bash
git add docker-compose.yml Dockerfile
git commit -m "feat: dual air-gap networks, entrypoint wizard, dashboard service"
```

- [ ] **Step 6: Push to GitHub**

```bash
git push origin feature/shieldlayer-implementation
```

---

## Final Verification Checklist

- [ ] `py -3.11 -m pytest tests/ -v` — all green
- [ ] `docker build -t shieldlayer-max:test .` — image builds cleanly
- [ ] `docker build -f Dockerfile.dashboard -t shieldlayer-dashboard:test .` — dashboard image builds
- [ ] `git log --oneline -10` — 8 clean commits
