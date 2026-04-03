# gateway/config.py
import os
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_TEST_SECRET = "a" * 64  # Used only when GATEWAY_TEST_MODE=1


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000

    # Required in production; defaults to test key in test mode
    secret_key: str = _TEST_SECRET if os.getenv("GATEWAY_TEST_MODE") == "1" else ""

    upstream_openai_base: str = "https://api.openai.com/v1"
    upstream_anthropic_base: str = "https://api.anthropic.com"

    redis_url: str = "redis://localhost:6379/0"
    vault_ttl: int = 300

    guardian_max_rewrites: int = 3
    cors_origins: str = "http://localhost:3000"  # comma-separated

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @model_validator(mode="after")
    def _validate_secret_key(self) -> "Settings":
        if os.getenv("GATEWAY_TEST_MODE") == "1":
            return self
        placeholder = "change-me-64-hex-chars-here-00000000000000000000000000000000"
        if not self.secret_key or len(self.secret_key) < 64 or self.secret_key == placeholder:
            raise ValueError(
                "SECRET_KEY must be set to a 64-char hex string. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return self


settings = Settings()
