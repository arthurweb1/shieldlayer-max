from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    vllm_base_url: str = "http://vllm:8000"
    vllm_model: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    vllm_guardian_model: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    postgres_dsn: str = "postgresql://shieldlayer:CHANGE_ME@postgres:5432/shieldlayer"
    shield_synonym_pairs_path: str = "/app/data/synonym_pairs.json"
    guardian_max_retries: int = 3
    audit_token: str = "change-me"
    cache_similarity_threshold: float = 0.97

    # LLM Backend Router
    llm_backend_type: str = "LOCAL"  # "LOCAL" (vLLM) or "CLOUD" (OpenAI-compatible)
    openai_api_key: str = ""          # Required when llm_backend_type=CLOUD
    openai_base_url: str = "https://api.openai.com/v1"  # Override for Azure/other providers

    # Vault
    vault_session_ttl_seconds: int = 300  # Auto-purge mapping after this many seconds

    # Setup / Config guard
    config_ready: bool = False
    compliance_strictness: str = "strict"
    postgres_ro_password: str = ""
    cloud_price_per_1k_tokens: float = 0.002


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Convenience alias for direct imports — tests should use get_settings() with override
settings = get_settings()
