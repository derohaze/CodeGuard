from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RuntimeSettingsResponse(BaseModel):
    default_preset: Literal["safe", "balanced", "aggressive"]
    default_scan_mode: Literal["fast", "deep"]
    auto_open_results: bool
    remember_sidebar_state: bool
    motion_profile: Literal["fluid", "reduced", "instant"]
    theme: Literal["light", "system"]
    surface_contrast: Literal["soft", "standard"]
    remediation_max_attempts: int = Field(ge=1, le=5)
    remediation_reuse_explanation: bool
    external_ingestion_max_rps: int = Field(ge=1, le=100)
    external_ingestion_retry_attempts: int = Field(ge=1, le=10)
    external_ingestion_backoff_seconds: float = Field(ge=0.1, le=30.0)
    updated_at: datetime


class UpdateRuntimeSettingsRequest(BaseModel):
    default_preset: Literal["safe", "balanced", "aggressive"] | None = None
    default_scan_mode: Literal["fast", "deep"] | None = None
    auto_open_results: bool | None = None
    remember_sidebar_state: bool | None = None
    motion_profile: Literal["fluid", "reduced", "instant"] | None = None
    theme: Literal["light", "system"] | None = None
    surface_contrast: Literal["soft", "standard"] | None = None
    remediation_max_attempts: int | None = Field(default=None, ge=1, le=5)
    remediation_reuse_explanation: bool | None = None
    external_ingestion_max_rps: int | None = Field(default=None, ge=1, le=100)
    external_ingestion_retry_attempts: int | None = Field(default=None, ge=1, le=10)
    external_ingestion_backoff_seconds: float | None = Field(default=None, ge=0.1, le=30.0)
