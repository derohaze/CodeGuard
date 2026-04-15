from __future__ import annotations

from app.core.config import get_settings
from app.domain.services.ai_client import SecurityAnalysisAIClient
from app.infrastructure.ai.nvidia_security_client import NvidiaSecurityClient


def build_ai_client() -> SecurityAnalysisAIClient:
    settings = get_settings()
    provider_order = [item.strip().lower() for item in settings.ai_provider_order if item.strip()]
    unsupported = [provider for provider in provider_order if provider not in {"nvidia", "security"}]
    if unsupported:
        raise RuntimeError("Only the security AI client entrypoint is supported by this backend.")

    for provider in provider_order or ["security"]:
        client = _build_provider(provider, settings)
        if client is not None:
            return client
    raise RuntimeError("No supported AI transport is configured. Set AI_SMALL_PROVIDER/AI_LARGE_PROVIDER and matching provider keys.")


def _build_provider(provider: str, settings) -> SecurityAnalysisAIClient | None:
    if provider in {"nvidia", "security"} and NvidiaSecurityClient.is_configured(settings):
        return NvidiaSecurityClient()
    return None
