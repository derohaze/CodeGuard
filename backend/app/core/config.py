from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="CodeGuard", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    api_workers: int = Field(default=1, alias="API_WORKERS")
    app_cors_origins: list[str] | str = Field(default="http://localhost:8080", alias="APP_CORS_ORIGINS")
    ai_provider_order: list[str] | str = Field(default="nvidia", alias="AI_PROVIDER_ORDER")

    nvidia_api_key: str | None = Field(default=None, alias="NVIDIA_API_KEY")
    nvidia_base_url: str = Field(default="https://integrate.api.nvidia.com/v1", alias="NVIDIA_BASE_URL")
    nvidia_model: str = Field(default="openai/gpt-oss-120b", alias="NVIDIA_MODEL")
    nvidia_small_model: str | None = Field(default=None, alias="NVIDIA_SMALL_MODEL")
    nvidia_large_model: str | None = Field(default=None, alias="NVIDIA_LARGE_MODEL")
    nvidia_overflow_model: str | None = Field(default=None, alias="NVIDIA_OVERFLOW_MODEL")
    nvidia_enable_thinking: bool = Field(default=True, alias="NVIDIA_ENABLE_THINKING")

    mongodb_uri: str = Field(alias="MONGODB_URI")
    mongodb_database: str = Field(default="CodeGuard", alias="MONGODB_DATABASE")
    mongodb_max_pool_size: int = Field(default=30, alias="MONGODB_MAX_POOL_SIZE")
    mongodb_min_pool_size: int = Field(default=5, alias="MONGODB_MIN_POOL_SIZE")
    mongodb_server_selection_timeout_ms: int = Field(default=3000, alias="MONGODB_SERVER_SELECTION_TIMEOUT_MS")
    queue_backend: str = Field(default="in_process", alias="QUEUE_BACKEND")
    auto_start_queue_worker: bool = Field(default=True, alias="AUTO_START_QUEUE_WORKER")
    scan_lock_backend: str = Field(default="auto", alias="SCAN_LOCK_BACKEND")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    scan_queue_name: str = Field(default="codeguard:queue:scan", alias="SCAN_QUEUE_NAME")
    ai_queue_name: str = Field(default="codeguard:queue:ai", alias="AI_QUEUE_NAME")
    verify_queue_name: str = Field(default="codeguard:queue:verify", alias="VERIFY_QUEUE_NAME")
    report_queue_name: str = Field(default="codeguard:queue:report", alias="REPORT_QUEUE_NAME")
    scan_job_timeout_seconds: int = Field(default=1800, alias="SCAN_JOB_TIMEOUT_SECONDS")
    worker_concurrency: int = Field(default=4, alias="WORKER_CONCURRENCY")
    worker_max_jobs: int = Field(default=4, alias="WORKER_MAX_JOBS")
    global_concurrent_scans_limit: int = Field(default=4, alias="GLOBAL_CONCURRENT_SCANS_LIMIT")
    session_scan_lock_ttl_seconds: int = Field(default=1800, alias="SESSION_SCAN_LOCK_TTL_SECONDS")
    source_scan_lock_ttl_seconds: int = Field(default=1800, alias="SOURCE_SCAN_LOCK_TTL_SECONDS")
    artifacts_dir: str = Field(
        default=str(Path(__file__).resolve().parents[2] / "artifacts"),
        alias="ARTIFACTS_DIR",
    )

    @field_validator("app_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: list[str] | str):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("ai_provider_order", mode="before")
    @classmethod
    def parse_provider_order(cls, value: list[str] | str):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("queue_backend", mode="before")
    @classmethod
    def normalize_queue_backend(cls, value: str):
        normalized = str(value).strip().lower()
        if normalized not in {"in_process", "arq"}:
            raise ValueError("QUEUE_BACKEND must be either 'in_process' or 'arq'.")
        return normalized

    @field_validator("scan_lock_backend", mode="before")
    @classmethod
    def normalize_scan_lock_backend(cls, value: str):
        normalized = str(value).strip().lower()
        if normalized not in {"auto", "in_memory", "redis"}:
            raise ValueError("SCAN_LOCK_BACKEND must be 'auto', 'in_memory', or 'redis'.")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
