from __future__ import annotations

import asyncio
import time
from typing import Any

from app.application.dto.runtime_settings_contracts import RuntimeSettingsResponse
from app.infrastructure.settings.runtime_settings_repository import RuntimeSettingsRepository


class RuntimeSettingsService:
    def __init__(
        self,
        repository: RuntimeSettingsRepository,
        *,
        cache_ttl_seconds: float = 2.0,
    ) -> None:
        self.repository = repository
        self.cache_ttl_seconds = max(0.5, float(cache_ttl_seconds))
        self._cache: RuntimeSettingsResponse | None = None
        self._cache_until = 0.0
        self._lock = asyncio.Lock()

    async def get(self) -> RuntimeSettingsResponse:
        now = time.monotonic()
        if self._cache is not None and now < self._cache_until:
            return self._cache

        async with self._lock:
            now = time.monotonic()
            if self._cache is not None and now < self._cache_until:
                return self._cache
            document = await self.repository.get()
            parsed = self._parse_document(document)
            self._cache = parsed
            self._cache_until = now + self.cache_ttl_seconds
            return parsed

    async def update(self, updates: dict[str, Any]) -> RuntimeSettingsResponse:
        payload = {
            key: value
            for key, value in updates.items()
            if value is not None
        }
        if not payload:
            return await self.get()

        document = await self.repository.update(payload)
        parsed = self._parse_document(document)
        async with self._lock:
            self._cache = parsed
            self._cache_until = time.monotonic() + self.cache_ttl_seconds
        return parsed

    @staticmethod
    def _parse_document(document: dict[str, Any]) -> RuntimeSettingsResponse:
        return RuntimeSettingsResponse(
            default_preset=str(document.get("default_preset", "balanced")),
            default_scan_mode=str(document.get("default_scan_mode", "deep")),
            auto_open_results=bool(document.get("auto_open_results", True)),
            remember_sidebar_state=bool(document.get("remember_sidebar_state", True)),
            motion_profile=str(document.get("motion_profile", "fluid")),
            theme=str(document.get("theme", "light")),
            surface_contrast=str(document.get("surface_contrast", "soft")),
            remediation_max_attempts=int(document.get("remediation_max_attempts", 3)),
            remediation_reuse_explanation=bool(document.get("remediation_reuse_explanation", True)),
            external_ingestion_max_rps=int(document.get("external_ingestion_max_rps", 10)),
            external_ingestion_retry_attempts=int(document.get("external_ingestion_retry_attempts", 3)),
            external_ingestion_backoff_seconds=float(document.get("external_ingestion_backoff_seconds", 0.5)),
            updated_at=document["updated_at"],
        )
