from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_base_url: str = "https://api.anthropic.com"
    redis_url: str = "redis://localhost:6379/0"
    redis_vault_ttl: int = 300
    faiss_index_path: str = "./data/faiss.index"
    faiss_dim: int = 1536
    semantic_cache_threshold: float = 0.92
    audit_log_path: str = "./data/audit.jsonl"
    dead_mans_ttl: int = 300
    presidio_models: list[str] = ["en_core_web_lg"]
    max_proxy_timeout: int = 120
    gateway_port: int = 8000
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
