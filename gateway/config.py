# gateway/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000
    secret_key: str = "a" * 64  # 64 hex chars (32 bytes) — override in .env

    upstream_openai_base: str = "https://api.openai.com/v1"
    upstream_anthropic_base: str = "https://api.anthropic.com"

    redis_url: str = "redis://localhost:6379/0"
    vault_ttl: int = 300

    guardian_max_rewrites: int = 3
    cors_origins: str = "http://localhost:3000"  # comma-separated

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
