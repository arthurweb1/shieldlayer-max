# ShieldLayer Max — Enterprise Governance Extension Design

**Date:** 2026-03-22
**Scope:** Three independent subsystems built in order B → A → C.

---

## Subsystem B: Multi-Tenancy, RBAC & Secure Cache ACL

### Goal
Add department-level identity to every request. Route LLM traffic per policy and prevent cross-department cache leakage.

### Data Model
Two headers are required on every `/v1/chat` request:
- `X-Org-ID` — department identifier string (e.g. `admin`, `rd`, `legal`)
- `X-User-Role` — role string, one of: `viewer`, `analyst`, `admin`

Role maps to numeric level: `viewer=0`, `analyst=1`, `admin=2`.

Missing or unknown values are rejected with HTTP 403.

### Auth Middleware (`app/middleware/auth.py`)
A FastAPI `BaseHTTPMiddleware` subclass extracts and validates both headers on every request. On success it attaches a `RequestIdentity(org_id: str, role: str, level: int)` dataclass to `request.state.identity`. Routes read from `request.state.identity`; they never re-parse headers. `/health` and `/metrics` are exempt from header validation.

### Policy Routing
`HybridRouter` gains a `route_for(identity: RequestIdentity) -> HybridRouter` instance method. It returns a **new `HybridRouter` instance** scoped to the correct backend:
- `identity.org_id == "admin"` → returns a LOCAL or CLOUD `HybridRouter` per `settings.llm_backend_type`
- All other orgs → always returns a LOCAL `HybridRouter` regardless of `settings.llm_backend_type`

`HybridRouter` constructor gains two optional named parameters to hold both configs:
- `local_config: dict | None = None` — `{"base_url": ..., "model": ...}`
- `cloud_config: dict | None = None` — `{"base_url": ..., "model": ..., "api_key": ...}`

When `route_for` is called, it instantiates a fresh single-backend `HybridRouter(backend_type=..., base_url=..., model=..., api_key=...)` using the appropriate config dict. The existing constructor signature (`backend_type`, `base_url`, `model`, `api_key`) is unchanged — the new `local_config`/`cloud_config` are only used by the dual-config instance created at startup.

**`main.py` lifespan update:** The `HybridRouter` constructed at startup must be a dual-config instance:
```python
_router = HybridRouter(
    backend_type=settings.llm_backend_type,
    base_url=settings.vllm_base_url if settings.llm_backend_type == "LOCAL" else settings.openai_base_url,
    model=settings.vllm_model,
    api_key=settings.openai_api_key,
    local_config={"base_url": settings.vllm_base_url, "model": settings.vllm_model},
    cloud_config={"base_url": settings.openai_base_url, "model": settings.vllm_model, "api_key": settings.openai_api_key},
)
```

In `routes.py`, the `chat` handler signature gains `request: Request` (FastAPI injects it automatically when declared). Identity is read from `request.state.identity`. The call site changes from:
```python
raw_response = await state.router.complete(masked_prompt)
```
to:
```python
identity = request.state.identity
raw_response = await state.router.route_for(identity).complete(masked_prompt)
```
The streaming path is updated identically (`route_for(identity).stream(...)`).

### Secure Semantic Cache ACL
`VectorCache` is extended with a permission level stored alongside each cached entry:
- `set(query, value, caller_level: int = 0)` — stores `caller_level` in a parallel `_levels: list[int]` list (same index as `_values`).
- `get(query, caller_level: int = 0)` — on a similarity hit, returns the cached value **only if `stored_level <= caller_level`** (higher-permission content is NOT visible to lower-permission callers; lower-permission content IS visible to higher-permission callers).
- Example: an `admin` (level 2) can see anything; a `viewer` (level 0) can only see level-0 cached entries.

The parameter is named `caller_level` throughout (not `min_level`) to prevent implementer confusion about comparison direction.

Existing calls to `get()` and `set()` without `caller_level` default to `0` (viewer-level) — backward-compatible.

### Error Codes
- `403` — missing or invalid `X-Org-ID` / `X-User-Role` headers
- `403` — org policy violation (attempted cloud access from non-admin org)

---

## Subsystem A: Guided Configuration Wizard

### Goal
Make initial setup zero-friction for non-technical admins. No manual `.env` editing required.

### CLI Wizard (`app/setup_wizard.py`)
A standalone Python script using `questionary` (terminal UI library). Runs when `.env` does not exist. Steps:

1. **GPU Detection** — runs `nvidia-smi` silently; asks "GPU detected — use vLLM for local inference?" (auto-skips to Ollama path if no GPU)
2. **Backend Mode** — "Local-only (air-gapped) or Hybrid-Cloud (OpenAI-compatible)?"
3. **Compliance Strictness** — three levels:
   - `LOW` — log only, no blocking
   - `MEDIUM` — standard Guardian filter (current behavior, `guardian_max_retries=2`)
   - `HIGH` — block on any suspicion (`guardian_max_retries=0`, block on first non-compliant signal)
4. **Security** — auto-generate `VAULT_ENCRYPTION_KEY` (32 random hex bytes via `secrets.token_hex(32)`), prompt user to set `AUDIT_TOKEN` (cannot be empty, cannot equal `"change-me"`)
5. **Postgres** — ask for password (default: `secrets.token_hex(16)`)
6. **Write `.env`** — validate all fields, write file atomically (write to `.env.tmp` then rename), print summary table

### `CONFIG_READY` Guard in FastAPI
`app/config.py` gains `config_ready: bool = False` (defaults `False`; wizard/setup writes `CONFIG_READY=true` to `.env`).

In `app/main.py`, the `lifespan` handler checks `config_ready` **first**:
- If `False`: skip all component initialization (no DB pool, no model loading). Register only a catch-all middleware that returns `{"detail": "Setup required. Visit http://localhost:8501"}` with HTTP 503 for all routes except `/health`. This prevents the DB connection from failing before the 503 can be served.
- If `True`: normal startup.

### Streamlit Setup UI (`dashboard/setup.py`)
A one-page Streamlit app replicating the wizard flow in the browser. Writes `.env` and sets `CONFIG_READY=true`. Used when users prefer a GUI over CLI.

### Docker Entrypoint (`entrypoint.sh`)
```sh
#!/bin/sh
set -e
if [ ! -f /app/.env ]; then
    echo "No .env found — running setup wizard..."
    python app/setup_wizard.py
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```
`docker-compose.yml` adds `entrypoint: ["/app/entrypoint.sh"]` to the `app` service.

### New Dashboard Docker Service
```yaml
dashboard:
  build:
    context: .
    dockerfile: Dockerfile.dashboard
  ports:
    - "8501:8501"
  env_file: .env
  depends_on:
    - postgres
  networks:
    - frontend_net
```

---

## Subsystem C: Guardian Analytics Dashboard

### Goal
A read-only Streamlit dashboard over the PostgreSQL audit log for C-level and compliance officers.

### Schema Additions to `audit_events`
Two new columns, both added with `IF NOT EXISTS` for idempotent startup:
```sql
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS pii_stats JSONB DEFAULT '{}';
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS cached BOOLEAN NOT NULL DEFAULT false;
```
Applied in `AuditLog.create()` alongside the existing `CREATE TABLE IF NOT EXISTS`.

`asyncpg` pool must register a JSONB codec so the column is returned as a Python dict (not a raw string). This is done by passing an `init` coroutine to `asyncpg.create_pool`:
```python
async def _init_conn(conn):
    await conn.set_type_codec(
        'jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog'
    )

pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10, init=_init_conn)
```
The `init` callback runs once per new connection when the pool opens it. The existing `AuditLog.create()` classmethod is updated to pass `init=_init_conn` to `create_pool`.

### `MaskResult` Update (`app/engine/shield.py`)
`MaskResult` dataclass gains a `pii_stats: dict[str, int]` field (entity_type → count). `ShieldEngine.mask()` populates it from the Presidio analyzer results. Example: `{"PERSON": 2, "EMAIL_ADDRESS": 1}`.

### `audit_log.write()` Signature Extension
New optional keyword argument: `pii_stats: dict | None = None`, `cached: bool = False`. Both are backward-compatible (existing call sites pass neither and get the defaults).

### `routes.py` — pass `pii_stats` and `cached` to audit
The chat handler passes `pii_stats=mask_result.pii_stats` and `cached=from_cache` to `audit.write()`.

### File: `dashboard/main.py`
Three panels using `st.columns`. Auto-refreshes every 30 seconds via `streamlit-autorefresh`.

**1. Cost-Savings Tracker**
- Queries: `SELECT COUNT(*) FROM audit_events WHERE cached=true AND ts >= NOW() - INTERVAL '1 day'`
- Estimates saved cost: `cache_hits × 500 × (CLOUD_PRICE_PER_1K_TOKENS / 1000)` (500 tokens = assumed avg request)
- Config: `CLOUD_PRICE_PER_1K_TOKENS` env var, default `0.002` (GPT-4o pricing)
- Displays: "Saved $X.XX today via semantic cache (N hits)"

**2. Compliance Heatmap**
- Queries `article_ref` distribution, last 30 days
- Radar chart (`plotly`) over Art. 5, Art. 10, Art. 12, Art. 13 — violation counts per article
- Bar chart: blocked (article_ref IS NOT NULL) vs compliant per day

**3. Privacy Metrics**
- Aggregates `pii_stats` JSONB across all rows in last 7 days
- Bar chart: entity type (PERSON, EMAIL, IBAN, etc.) vs count
- Counter: total PII entities masked all-time

### Read-Only DB Access
Dashboard container uses a read-only PostgreSQL user `shieldlayer_ro` created at startup by the app's `AuditLog.create()`:
```python
# Executed in AuditLog.create() after table creation
# ro_password = settings.postgres_ro_password
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
```
Note: f-string interpolation is acceptable here because `ro_password` comes from a trusted admin-controlled env var, not user input.
Config: `POSTGRES_RO_PASSWORD` env var (default: `"readonly"`). The RO role SQL uses the value from `settings.postgres_ro_password` via Python string interpolation before execution — not hardcoded. Dashboard uses `POSTGRES_RO_DSN` constructed from it.

---

## Air-Gap Network Isolation (Docker Compose)

Two isolated Docker networks replace the default single network:

```yaml
networks:
  frontend_net:
    driver: bridge
  inference_net:
    driver: bridge
    internal: true   # no external gateway — vLLM cannot reach the internet
```

Service network assignments:
- `postgres`: `frontend_net` only
- `vllm`: `inference_net` only
- `app`: **both** `frontend_net` + `inference_net` (the only bridge between the two)
- `dashboard`: `frontend_net` only

**Migration note:** This is a breaking change to the network topology. It requires a full service restart: `docker-compose down && docker-compose up -d`. A rolling update is not possible.

---

## Dependencies Added

| File | Package | Version | Purpose |
|------|---------|---------|---------|
| `requirements.txt` | `questionary` | `2.0.1` | CLI wizard prompts |
| `requirements-dashboard.txt` | `streamlit` | `1.35.0` | Web setup UI + analytics |
| `requirements-dashboard.txt` | `plotly` | `5.22.0` | Radar/bar charts |
| `requirements-dashboard.txt` | `streamlit-autorefresh` | `1.0.1` | 30s auto-refresh |
| `requirements-dashboard.txt` | `asyncpg` | `0.29.0` | Dashboard DB reads |

---

## Files Created / Modified

| File | Action |
|------|--------|
| `app/middleware/__init__.py` | Create |
| `app/middleware/auth.py` | Create — RBAC middleware + `RequestIdentity` |
| `app/engine/shield.py` | Modify — `MaskResult` gains `pii_stats: dict[str, int]` |
| `app/engine/router.py` | Modify — add `route_for(identity)` returning new `HybridRouter` |
| `app/database/vector_cache.py` | Modify — `caller_level` ACL on `get()`/`set()` |
| `app/database/audit_log.py` | Modify — `pii_stats` + `cached` columns, JSONB codec, RO user |
| `app/api/routes.py` | Modify — identity, per-request router, cache ACL, pii_stats/cached in audit |
| `app/main.py` | Modify — register middleware, `config_ready` guard, skip init when False |
| `app/config.py` | Modify — `config_ready`, `compliance_strictness`, `cloud_price_per_1k_tokens`, `postgres_ro_password` |
| `app/setup_wizard.py` | Create |
| `entrypoint.sh` | Create |
| `dashboard/__init__.py` | Create |
| `dashboard/setup.py` | Create — Streamlit setup UI |
| `dashboard/main.py` | Create — analytics dashboard |
| `docker-compose.yml` | Modify — dual networks, entrypoint, dashboard service |
| `Dockerfile.dashboard` | Create |
| `requirements-dashboard.txt` | Create |
| `tests/test_auth.py` | Create |
| `tests/test_vector_cache.py` | Modify — ACL tests |
| `tests/test_routes.py` | Modify — identity header tests |
| `tests/test_shield.py` | Modify — `pii_stats` in `MaskResult` |

---

## Out of Scope
- OAuth / SSO integration (headers are trusted — enforcement is at the load balancer)
- Per-user audit log queries (audit is org-scoped, not user-scoped)
- Real-time streaming of dashboard metrics (30s auto-refresh is sufficient)
- Multi-instance FAISS cache sync (each instance has its own in-process cache)
