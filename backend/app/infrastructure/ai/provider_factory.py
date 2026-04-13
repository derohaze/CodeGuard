from __future__ import annotations

from app.core.config import get_settings
from app.domain.services.ai_client import SecurityAnalysisAIClient
from app.infrastructure.ai.nvidia_security_client import NvidiaSecurityClient


def build_ai_client() -> SecurityAnalysisAIClient:
    settings = get_settings()
    provider_order = [item.strip().lower() for item in settings.ai_provider_order if item.strip()]
    unsupported = [provider for provider in provider_order if provider != "nvidia"]
    if unsupported:
        raise RuntimeError("Only the NVIDIA AI provider is supported by this backend.")

    client = _build_provider("nvidia", settings)
    if client is None:
        raise RuntimeError("NVIDIA is not configured. Set NVIDIA_API_KEY.")
    return client


def _build_provider(provider: str, settings) -> SecurityAnalysisAIClient | None:
    if provider == "nvidia" and settings.nvidia_api_key:
        return NvidiaSecurityClient()
    return None
