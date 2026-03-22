# shieldlayer-max

> On-premise AI proxy that enforces EU AI Act compliance — anonymizing PII before LLM calls, auditing every response, and watermarking outputs for forensic traceability. No data leaves your server.

---

## How it works

```
Your App  →  shieldlayer-max  →  Local LLM  →  shieldlayer-max  →  Your App
              (masks names,         (no PII        (restores names,
               emails, IBANs)        visible)        adds audit log)
```

**Step by step:**
1. Your request comes in — names, emails, IBANs are replaced with placeholders (`PERSON_001`, `EMAIL_001`)
2. The masked prompt is sent to a local LLM (nothing leaves your server)
3. The response is checked for EU AI Act violations — blocked if non-compliant (HTTP 451)
4. Original values are re-inserted into the response
5. A hidden watermark is added so leaked responses can be traced back
6. Everything is logged to a local database for audit purposes

---

## Quick Start

### Option A — With GPU (recommended for production)

Requires an NVIDIA GPU with CUDA 12.1+.

```bash
git clone https://github.com/arthurweb1/shieldlayer-max.git
cd shieldlayer-max
git checkout feature/shieldlayer-implementation

# Copy and edit config
cp .env.example .env
# Open .env and change: POSTGRES_PASSWORD, AUDIT_TOKEN, VLLM_MODEL

# Download model weights once (~16 GB)
pip install huggingface_hub[cli]
huggingface-cli download meta-llama/Meta-Llama-3-8B-Instruct

# Start everything
docker compose up -d
```

### Option B — Without GPU (CPU / Ollama)

No NVIDIA GPU? Use [Ollama](https://ollama.com) as a local LLM backend instead of vLLM.

**1. Install Ollama:** https://ollama.com/download

**2. Pull a small model (e.g. Mistral 7B ~4 GB):**
```bash
ollama pull mistral
```

**3. Edit `.env`** — point shieldlayer-max at Ollama instead of vLLM:
```env
VLLM_BASE_URL=http://host.docker.internal:11434
VLLM_MODEL=mistral
VLLM_GUARDIAN_MODEL=mistral
```

**4. Edit `docker-compose.yml`** — remove the `vllm` service entirely (Ollama runs natively on your machine):
```yaml
# Delete or comment out the entire vllm: block
```

**5. Start:**
```bash
docker compose up -d postgres app
```

> **Note:** CPU inference is slower (30–120 seconds per response depending on hardware). GPU is recommended for any production use.

---

### Test the proxy

**Linux / macOS / Git Bash:**
```bash
curl -X POST http://localhost:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Max Mustermann at max@example.com needs GDPR advice."}]}'
```

**Windows PowerShell:**
```powershell
Invoke-WebRequest -Method POST http://localhost:8080/v1/chat `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"messages": [{"role": "user", "content": "Max Mustermann at max@example.com needs GDPR advice."}]}'
```

**Expected response:**
```json
{
  "id": "...",
  "content": "Max Mustermann should consider...",
  "compliance": {"compliant": true, "article": null, "retries": 0},
  "cached": false
}
```
Notice: `max@example.com` and `Max Mustermann` were never sent to the LLM — only `EMAIL_001` and `PERSON_001` were.

---

## Prerequisites

| What | Details |
|------|---------|
| **Docker Desktop** | Download at [docker.com](https://www.docker.com/products/docker-desktop/) |
| **Docker Compose** | Included with Docker Desktop (v2.0+) |
| **LLM Backend** | Either: NVIDIA GPU + vLLM **or** CPU + Ollama (see Quick Start above) |
| **Disk space** | ~4 GB for Ollama/Mistral, ~16 GB for Llama-3-8B |
| **Python 3.11** | Only needed for local development — not required to run via Docker |

**Optional (GPU path only):**
- NVIDIA GPU with CUDA 12.1+
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

---

## Configuration (`.env`)

Copy `.env.example` to `.env` and change these values:

| Variable | What to set | Default |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | **Change this!** Any strong password | `CHANGE_ME` |
| `AUDIT_TOKEN` | **Change this!** Random string for PDF export auth | `change-me-to-a-secure-token` |
| `VLLM_MODEL` | Model name (must match downloaded model) | `meta-llama/Meta-Llama-3-8B-Instruct` |
| `VLLM_BASE_URL` | LLM server URL (change if using Ollama) | `http://vllm:8000` |

All other variables can stay at their defaults for a basic setup.

<details>
<summary>Full environment variable reference</summary>

| Variable | Description | Default |
|----------|-------------|---------|
| `VLLM_BASE_URL` | LLM server URL | `http://vllm:8000` |
| `VLLM_MODEL` | Model for main inference | `meta-llama/Meta-Llama-3-8B-Instruct` |
| `VLLM_GUARDIAN_MODEL` | Model for compliance checking (can be same) | `meta-llama/Meta-Llama-3-8B-Instruct` |
| `POSTGRES_DSN` | Full PostgreSQL connection string | auto-built from other vars |
| `SHIELD_SYNONYM_PAIRS_PATH` | Path to watermark word pairs | `/app/data/synonym_pairs.json` |
| `GUARDIAN_MAX_RETRIES` | Self-correction attempts before blocking | `3` |
| `AUDIT_TOKEN` | Bearer token for `/audit/export` | *(set a strong value)* |
| `CACHE_SIMILARITY_THRESHOLD` | How similar two prompts must be to share a cached answer | `0.97` |
| `HF_HOME` | Hugging Face model cache directory | `~/.cache/huggingface` |
| `POSTGRES_USER` | Database username | `shieldlayer` |
| `POSTGRES_PASSWORD` | Database password | `CHANGE_ME` |
| `POSTGRES_DB` | Database name | `shieldlayer` |

</details>

---

## EU AI Act Compliance

shieldlayer-max directly addresses the following obligations:

- **Art. 5 — Prohibited Practices**: The Guardian judge detects and blocks responses that could constitute manipulation, exploitation of vulnerabilities, or subliminal techniques. Blocked requests return HTTP 451 (Unavailable For Legal Reasons) with article reference.

- **Art. 10 — Data Governance**: PII masking via Microsoft Presidio ensures training-quality data hygiene. The double-blind pseudonymization scheme guarantees that personally identifiable data never enters the LLM context.

- **Art. 12 — Record-Keeping**: Every request is logged to an append-only PostgreSQL audit table (hashed prompts, compliance results, article references, timestamps). Audit records are exportable as PDF via `GET /audit/export`.

- **Art. 13 — Transparency**: Every response includes a `compliance` field in the JSON payload. The Guardian's compliance assessment is recorded per-request, enabling downstream transparency obligations.

---

## Forensic Watermarking

Every response contains a hidden linguistic watermark. Using a deterministic seed based on the `request_id` (stored in the audit log), synonym substitutions are applied to the text (e.g. "however" → "nevertheless"). If a response is ever leaked, the watermark can be matched against the audit log to identify which session it came from — without storing any plaintext.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/chat` | Send a prompt through the compliance pipeline |
| `GET` | `/audit/export` | Download PDF audit log (`Authorization: Bearer <AUDIT_TOKEN>`) |
| `GET` | `/health` | Health check |

**Error codes:**
- `451` — Response blocked (EU AI Act violation detected, article reference in body)
- `500` — Audit write failure (compliance logging is mandatory per Art. 12)

---

## License

MIT License — see [LICENSE](LICENSE) for details.
