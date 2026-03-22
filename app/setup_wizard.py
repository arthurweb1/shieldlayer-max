"""Interactive CLI setup wizard for ShieldLayer Max.

Run directly:  python -m app.setup_wizard
Or via entrypoint when .env is missing.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import questionary
from questionary import Style

ENV_PATH = Path(".env")

WIZARD_STYLE = Style(
    [
        ("qmark",        "fg:#DFFF00 bold"),
        ("question",     "bold"),
        ("answer",       "fg:#DFFF00 bold"),
        ("pointer",      "fg:#DFFF00 bold"),
        ("highlighted",  "fg:#DFFF00 bold"),
        ("selected",     "fg:#DFFF00"),
        ("separator",    "fg:#666666"),
        ("instruction",  "fg:#888888"),
        ("text",         ""),
        ("disabled",     "fg:#858585 italic"),
    ]
)


def _has_gpu() -> bool:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def run_wizard() -> None:
    print("\n  ■ ShieldLayer Max — Enterprise Setup Wizard\n")

    # --- LLM backend ---
    backend = questionary.select(
        "LLM backend:",
        choices=["LOCAL (vLLM)", "CLOUD (OpenAI-compatible)"],
        style=WIZARD_STYLE,
    ).ask()

    if backend is None:
        sys.exit(0)

    use_cloud = backend.startswith("CLOUD")

    # --- Collect config values ---
    if use_cloud:
        openai_base_url = questionary.text(
            "OpenAI-compatible base URL:",
            default="https://api.openai.com/v1",
            style=WIZARD_STYLE,
        ).ask() or "https://api.openai.com/v1"

        openai_api_key = questionary.password(
            "API key:",
            style=WIZARD_STYLE,
        ).ask() or ""

        model = questionary.text(
            "Model name:",
            default="gpt-4o",
            style=WIZARD_STYLE,
        ).ask() or "gpt-4o"

        llm_backend_type = "CLOUD"
        vllm_base_url = "http://vllm:8000/v1"
        vllm_model = model
    else:
        gpu_detected = _has_gpu()
        gpu_label = "(GPU detected)" if gpu_detected else "(no GPU — CPU inference will be slow)"
        questionary.print(f"  Local vLLM mode {gpu_label}", style="fg:#888888")

        vllm_base_url = questionary.text(
            "vLLM base URL:",
            default="http://vllm:8000/v1",
            style=WIZARD_STYLE,
        ).ask() or "http://vllm:8000/v1"

        vllm_model = questionary.text(
            "Model name:",
            default="mistralai/Mistral-7B-Instruct-v0.2",
            style=WIZARD_STYLE,
        ).ask() or "mistralai/Mistral-7B-Instruct-v0.2"

        openai_base_url = vllm_base_url
        openai_api_key = ""
        model = vllm_model
        llm_backend_type = "LOCAL"

    # --- PostgreSQL ---
    postgres_dsn = questionary.text(
        "PostgreSQL DSN:",
        default="postgresql://shieldlayer:shieldlayer@postgres:5432/shieldlayer",
        style=WIZARD_STYLE,
    ).ask() or "postgresql://shieldlayer:shieldlayer@postgres:5432/shieldlayer"

    postgres_ro_password = questionary.password(
        "Read-only DB user password (for dashboard):",
        style=WIZARD_STYLE,
    ).ask() or "readonly_secret"

    # --- Compliance ---
    strictness = questionary.select(
        "EU AI Act compliance strictness:",
        choices=["strict", "moderate", "audit-only"],
        default="strict",
        style=WIZARD_STYLE,
    ).ask() or "strict"

    # --- Audit token ---
    audit_token = questionary.password(
        "Audit export token (used by /audit/export):",
        style=WIZARD_STYLE,
    ).ask() or "changeme"

    # --- Write .env ---
    env_lines = [
        f"CONFIG_READY=true",
        f"LLM_BACKEND_TYPE={llm_backend_type}",
        f"VLLM_BASE_URL={vllm_base_url}",
        f"VLLM_MODEL={vllm_model}",
        f"OPENAI_BASE_URL={openai_base_url}",
        f"OPENAI_API_KEY={openai_api_key}",
        f"POSTGRES_DSN={postgres_dsn}",
        f"POSTGRES_RO_PASSWORD={postgres_ro_password}",
        f"COMPLIANCE_STRICTNESS={strictness}",
        f"AUDIT_TOKEN={audit_token}",
    ]

    ENV_PATH.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    print(f"\n  ✓ Configuration written to {ENV_PATH.resolve()}\n")


if __name__ == "__main__":
    run_wizard()
