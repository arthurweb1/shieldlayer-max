"""Streamlit web setup UI — alternative to CLI wizard for non-terminal environments."""
import os
from pathlib import Path

import streamlit as st

ENV_PATH = Path(".env")

st.set_page_config(
    page_title="ShieldLayer Max — Setup",
    page_icon="🛡",
    layout="centered",
)

# ── Custom CSS: Obsidian Vault theme ─────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://api.fontshare.com/v2/css?f[]=clash-display@700&display=swap');
  .stApp { background: #0D0D0D; }
  h1, h2, h3 { font-family: 'Clash Display', sans-serif; color: #DFFF00; }
  .stButton > button {
    background: #DFFF00; color: #0D0D0D;
    border: none; font-weight: 700; letter-spacing: 0.1em;
  }
  .stButton > button:hover { background: transparent; color: #DFFF00; border: 1px solid #DFFF00; }
</style>
""", unsafe_allow_html=True)

st.title("■ ShieldLayer Max")
st.subheader("Enterprise Setup Wizard")

if ENV_PATH.exists():
    st.success(f"✓ Configuration already exists at `{ENV_PATH.resolve()}`")
    st.info("Delete `.env` and restart to re-run setup.")
    st.stop()

with st.form("setup_form"):
    st.markdown("### LLM Backend")
    backend = st.selectbox("Backend type", ["LOCAL (vLLM)", "CLOUD (OpenAI-compatible)"])
    use_cloud = backend.startswith("CLOUD")

    if use_cloud:
        openai_base_url = st.text_input("OpenAI-compatible base URL", "https://api.openai.com/v1")
        openai_api_key  = st.text_input("API key", type="password")
        model           = st.text_input("Model name", "gpt-4o")
        vllm_base_url   = "http://vllm:8000/v1"
        llm_backend_type = "CLOUD"
    else:
        vllm_base_url    = st.text_input("vLLM base URL", "http://vllm:8000/v1")
        model            = st.text_input("Model name", "mistralai/Mistral-7B-Instruct-v0.2")
        openai_base_url  = vllm_base_url
        openai_api_key   = ""
        llm_backend_type = "LOCAL"

    st.markdown("### Database")
    postgres_dsn         = st.text_input("PostgreSQL DSN", "postgresql://shieldlayer:shieldlayer@postgres:5432/shieldlayer")
    postgres_ro_password = st.text_input("Read-only user password", type="password", value="readonly_secret")

    st.markdown("### Compliance")
    strictness  = st.selectbox("EU AI Act strictness", ["strict", "moderate", "audit-only"])
    audit_token = st.text_input("Audit export token", type="password", value="changeme")

    submitted = st.form_submit_button("■ Save Configuration")

if submitted:
    env_lines = [
        "CONFIG_READY=true",
        f"LLM_BACKEND_TYPE={llm_backend_type}",
        f"VLLM_BASE_URL={vllm_base_url}",
        f"VLLM_MODEL={model}",
        f"OPENAI_BASE_URL={openai_base_url}",
        f"OPENAI_API_KEY={openai_api_key}",
        f"POSTGRES_DSN={postgres_dsn}",
        f"POSTGRES_RO_PASSWORD={postgres_ro_password}",
        f"COMPLIANCE_STRICTNESS={strictness}",
        f"AUDIT_TOKEN={audit_token}",
    ]
    ENV_PATH.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    st.success(f"✓ Configuration written to `{ENV_PATH.resolve()}`")
    st.info("Restart the ShieldLayer Max service to apply.")
