# ShieldLayer Max

**Enterprise AI Gateway for EU AI Act compliance.**

Drop-in OpenAI/Anthropic-compatible proxy that masks PII, enforces EU AI Act rules, watermarks every response, and generates forensic audit trails — in under 2ms. No plaintext leaves your server.

[![Deploy to GitHub Pages](https://github.com/arthurweb1/shieldlayer-max/actions/workflows/pages.yml/badge.svg)](https://github.com/arthurweb1/shieldlayer-max/actions/workflows/pages.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![EU AI Act Ready](https://img.shields.io/badge/EU%20AI%20Act-Ready-brightgreen)](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689)

🌐 **Live:** [arthurweb1.github.io/shieldlayer-max](https://arthurweb1.github.io/shieldlayer-max)

---

## How It Works

1. **PII Anonymization** — Microsoft Presidio scans every inbound prompt and replaces names, e-mail addresses, IBANs, and other entities with deterministic placeholders (`PERSON_001`, `EMAIL_001`). The LLM never sees raw personal data.

2. **Zero-Persistence Vault** — The placeholder-to-PII mapping is encrypted with AES-256-GCM and held exclusively in RAM. Keys are zeroed via `ctypes.memset` after use. The Vault enforces a 300-second TTL; no mapping survives a process restart.

3. **Semantic Cache** — The masked prompt is embedded and compared against the FAISS index using cosine similarity. If a prior response scores 0.97 or higher, it is returned immediately — bypassing the LLM call entirely.

4. **HybridRouter** — On a cache miss, the router selects either the LOCAL backend (vLLM, on-premise GPU) or the CLOUD backend (any OpenAI-compatible API). All traffic to the cloud backend is already anonymized at this point.

5. **Guardian Compliance Judge** — The raw LLM response is evaluated against EU AI Act Articles 5, 10, 12, and 13. If a violation is detected, the Guardian triggers a self-correction loop (up to `GUARDIAN_MAX_RETRIES` attempts). Responses that remain non-compliant are blocked with HTTP 451.

6. **De-anonymization** — Approved responses pass back through the Vault: placeholders are replaced with the original PII values. The mapping is then zeroed from memory.

7. **Forensic Watermarking** — A deterministic synonym substitution (seeded by `request_id`) is applied to the response text. If a response is ever leaked, the watermark identifies the originating session without storing any plaintext.

8. **Audit Trail** — Only SHA-256 hashes of the prompt and response, together with compliance metadata, are written to the audit log. No plaintext prompt, no plaintext response, and no PII mapping is ever persisted to disk.

---

## Stack

| Layer | Technology |
|---|---|
| **Gateway** | FastAPI, Python, Redis, Presidio, AES-256-GCM |
| **Dashboard** | Next.js 15, Tailwind v4, Vitest, WebSocket |
| **Extension** | Chrome MV3, TypeScript, tsup |
| **Website** | Next.js 15, Framer Motion → GitHub Pages |

---

## Project Structure

```
.worktrees/implement/
├── gateway/          # FastAPI AI Gateway (Python)
│   ├── anonymizer/   # Presidio PII engine + Redis vault
│   ├── compliance/   # EU AI Act Guardian Judge
│   ├── watermark/    # Forensic watermark engine
│   ├── metrics/      # WebSocket metrics store
│   └── audit/        # Immutable audit log
├── dashboard-next/   # Next.js 15 real-time dashboard
├── extension/        # Chrome MV3 Ghost Mode extension
└── website/          # Marketing site (GitHub Pages)
```

---

## Quick Start

**Drop-in usage — one line change:**

```python
# Before
client = OpenAI(base_url="https://api.openai.com/v1")

# After — full EU AI Act compliance, PII masking, audit trail
client = OpenAI(base_url="http://localhost:8000/v1")
```

### Prerequisites

| Requirement | Details |
|-------------|---------|
| Docker Desktop | [docker.com](https://www.docker.com/products/docker-desktop/) |
| Docker Compose | Included with Docker Desktop v2.0+ |
| LLM Backend | NVIDIA GPU + vLLM **or** CPU + Ollama |

### Option A — GPU (vLLM, recommended for production)

```bash
git clone https://github.com/arthurweb1/shieldlayer-max.git
cd shieldlayer-max
git checkout feature/shieldlayer-implementation

cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD, AUDIT_TOKEN, VLLM_MODEL

huggingface-cli download meta-llama/Meta-Llama-3-8B-Instruct
docker compose up -d
```

### Option B — CPU / Ollama (no GPU required)

```bash
ollama pull mistral
# Set LLM_BACKEND_TYPE=local, VLLM_BASE_URL=http://host.docker.internal:11434 in .env
docker compose up -d postgres app
```

### Test the proxy

```bash
curl -X POST http://localhost:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Max Mustermann at max@example.com needs GDPR advice."}]}'
```

### Load the Chrome Extension

1. `chrome://extensions/` → Enable Developer Mode
2. **Load unpacked** → select the `extension/` folder

---

## EU AI Act Coverage

| Article | Requirement | Implementation |
|---|---|---|
| Art. 5 | Prohibited practices (subliminal, manipulation, social credit) | Guardian Judge — HTTP 451 on violation |
| Art. 10 | Data governance | Presidio PII masking + AES-256-GCM RAM vault |
| Art. 12 | Transparency & traceability | SHA-256 audit log + forensic watermark |
| Art. 13 | Transparency obligations | `compliance` field in every response |

---

## In-Memory-Only Policy

- **AES-256-GCM in RAM** — PII mappings are never serialized to disk, swap, or logs
- **Key zeroing** — Encryption keys overwritten with zeros via `ctypes.memset` after each use
- **TTL: 300s** — Vault entries auto-purge; a process restart clears everything
- **No plaintext persistence** — Only SHA-256 hashes reach the audit database

---

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/v1/chat/completions` | — | OpenAI-compatible proxy endpoint |
| `GET` | `/v1/metrics` | — | Live metrics snapshot |
| `WS` | `/v1/metrics/ws` | — | WebSocket real-time metrics feed |
| `GET` | `/v1/audit` | — | Audit log entries |
| `GET` | `/health` | — | Liveness check |

**HTTP status codes:**

| Code | Meaning |
|------|---------|
| `200` | Success |
| `451` | Blocked — EU AI Act violation (article reference in body) |
| `500` | Audit write failure (compliance logging is mandatory per Art. 12) |

---

## Configuration

Copy `.env.example` to `.env.local` and set the required values.

| Variable | Description | Default |
|----------|-------------|---------|
| `GATEWAY_TEST_MODE` | Set to `1` for local dev (skips key validation) | — |
| `SECRET_KEY` | 64-char hex string for AES key derivation | required in prod |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |
| `UPSTREAM_OPENAI_BASE` | OpenAI-compatible upstream | `https://api.openai.com` |
| `UPSTREAM_ANTHROPIC_BASE` | Anthropic upstream | `https://api.anthropic.com` |

---

## License

MIT — see [LICENSE](LICENSE)
