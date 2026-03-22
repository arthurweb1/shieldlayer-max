from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    vllm_base_url: str = "http://vllm:8000"
    vllm_model: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    vllm_guardian_model: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    postgres_dsn: str = "postgresql://shieldlayer:CHANGE_ME@postgres:5432/shieldlayer"
    shield_synonym_pairs_path: str = "/app/data/synonym_pairs.json"
    guardian_max_retries: int = 3
    audit_token: str = "change-me"
    cache_similarity_threshold: float = 0.97

    class Config:
        env_file = ".env"


settings = Settings()
