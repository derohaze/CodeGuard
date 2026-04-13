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


@lru_cache
def get_settings() -> Settings:
    return Settings()
