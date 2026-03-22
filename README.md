# shieldlayer-max

> On-premise AI proxy that enforces EU AI Act compliance — anonymizing PII before LLM calls, auditing every response, and watermarking outputs for forensic traceability. No data leaves your server.

---

## Architecture

```
Client Request
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI (port 8080)                   │
│                                                         │
│  ┌────────────┐   ┌─────────────────┐   ┌───────────┐  │
│  │   Shield   │   │  Semantic Cache  │   │  Guardian │  │
│  │ (Presidio) │   │  (FAISS + ST)   │   │ (vLLM)   │  │
│  └─────┬──────┘   └────────┬────────┘   └─────┬─────┘  │
│        │ PII masked        │ cache miss        │        │
│        ▼                   ▼                   ▼        │
│  ┌─────────────────────────────────────────────────┐    │
│  │              vLLM (local GPU inference)          │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌────────────────────────────────────────────────┐     │
│  │  Audit Log (PostgreSQL) — append-only, hashed  │     │
│  └────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

**Request pipeline:**
1. Presidio detects and pseudonymizes PII (names, IBANs, emails) — **data never leaves the shield**
2. FAISS semantic cache checks for near-identical prior requests (threshold: 0.97 cosine)
3. Masked prompt sent to local vLLM instance
4. Guardian judge checks output for EU AI Act violations (Art. 5, 10, 13)
5. Non-compliant responses trigger up to 3 correction attempts before returning HTTP 451
6. PII re-injected into response (de-anonymization)
7. Linguistic watermark injected — every response is forensically traceable
8. Full audit record written to PostgreSQL (required by EU AI Act Art. 12)

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Docker + Docker Compose | v2.0+ |
| NVIDIA GPU | Required for vLLM inference (CUDA 12.1+) |
| NVIDIA Container Toolkit | `nvidia-container-toolkit` installed |
| LLM model weights | Download once (e.g. Llama-3-8B-Instruct via `huggingface-cli download`) |
| Python 3.11 | For local development only — production runs in Docker |

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/arthurweb1/shieldlayer-max.git
cd shieldlayer-max

# 2. Configure environment
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD, AUDIT_TOKEN, and VLLM_MODEL path

# 3. Download model weights (one-time, ~16GB for Llama-3-8B)
huggingface-cli download meta-llama/Meta-Llama-3-8B-Instruct

# 4. Start all services
docker compose up -d

# 5. Test the proxy
curl -X POST http://localhost:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Max Mustermann at max@example.com needs GDPR advice."}]}'
```

**Expected response:** JSON with `content` (PII replaced back after masked LLM call), `compliance.compliant: true`, and `cached: false`.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VLLM_BASE_URL` | vLLM server URL | `http://vllm:8000` |
| `VLLM_MODEL` | Model name for main inference | `meta-llama/Meta-Llama-3-8B-Instruct` |
| `VLLM_GUARDIAN_MODEL` | Model for compliance checking (can be same as VLLM_MODEL) | `meta-llama/Meta-Llama-3-8B-Instruct` |
| `POSTGRES_DSN` | PostgreSQL connection string | `postgresql://shieldlayer:CHANGE_ME@postgres:5432/shieldlayer` |
| `SHIELD_SYNONYM_PAIRS_PATH` | Path to watermark synonym pairs JSON | `/app/data/synonym_pairs.json` |
| `GUARDIAN_MAX_RETRIES` | Max self-correction attempts before HTTP 451 | `3` |
| `AUDIT_TOKEN` | Bearer token for `/audit/export` endpoint | *(set to strong random value)* |
| `CACHE_SIMILARITY_THRESHOLD` | Cosine similarity threshold for cache hits | `0.97` |
| `HF_HOME` | Hugging Face model cache directory | `~/.cache/huggingface` |
| `POSTGRES_USER` | PostgreSQL username | `shieldlayer` |
| `POSTGRES_PASSWORD` | PostgreSQL password — **change before deploying** | `CHANGE_ME` |
| `POSTGRES_DB` | PostgreSQL database name | `shieldlayer` |

---

## EU AI Act Compliance

shieldlayer-max directly addresses the following obligations:

- **Art. 5 — Prohibited Practices**: The Guardian judge detects and blocks responses that could constitute manipulation, exploitation of vulnerabilities, or subliminal techniques. Blocked requests return HTTP 451 (Unavailable For Legal Reasons) with article reference.

- **Art. 10 — Data Governance**: PII masking via Microsoft Presidio ensures training-quality data hygiene. The double-blind pseudonymization scheme guarantees that personally identifiable data never enters the LLM context.

- **Art. 12 — Record-Keeping**: Every request is logged to an append-only PostgreSQL audit table (hashed prompts, compliance results, article references, timestamps). Audit records are exportable as PDF via `GET /audit/export`.

- **Art. 13 — Transparency**: Every response includes a `compliance` field in the JSON payload. The Guardian's compliance assessment is recorded per-request, enabling downstream transparency obligations.

---

## Forensic Watermarking

Every response generated by shieldlayer-max contains a hidden linguistic watermark. Using a deterministic seed derived from the `request_id` (stored in the audit log), synonym substitutions are applied to the response text. If a response is leaked, the watermark seed can be recovered from the audit log and used to identify the originating session.

**How it works:**
- Seed: `SHA256(request_id)[:8]`
- Method: Synonym substitution from 54 word pairs (e.g. "however" ↔ "nevertheless")
- Fallback: If fewer than 3 substitutions are possible, a disclosure statement is appended
- Detection: Given the seed, any forensic analyst can verify which session produced a response

This mechanism provides legal accountability without requiring plaintext storage of prompts or responses.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/chat` | Proxy chat request through the full compliance pipeline |
| `GET` | `/audit/export` | Download PDF audit report (`Authorization: Bearer <AUDIT_TOKEN>`) |
| `GET` | `/health` | Liveness check |

### POST /v1/chat

**Request:**
```json
{
  "messages": [{"role": "user", "content": "your prompt"}],
  "stream": false
}
```

**Response:**
```json
{
  "id": "uuid",
  "content": "response text",
  "compliance": {"compliant": true, "article": null, "retries": 0},
  "cached": false
}
```

**Error codes:**
- `451` — Response blocked by compliance guardian (body contains article reference)
- `500` — Audit write failure (EU AI Act Art. 12 critical path)

---

## License

MIT License — see [LICENSE](LICENSE) for details.
