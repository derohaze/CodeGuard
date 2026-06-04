from __future__ import annotations

import httpx
import pytest

from app.core.exceptions import ExternalAIServiceError
from app.infrastructure.ai.nvidia_security_client import (
    NvidiaSecurityClient,
    _ProviderTarget,
    _map_provider_http_error,
)


def test_rate_limit_error_preserves_retry_after_seconds() -> None:
    response = httpx.Response(
        429,
        headers={"Retry-After": "12"},
        json={"error": {"message": "quota exceeded"}},
        request=httpx.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions"),
    )

    error = _map_provider_http_error("nvidia", response)

    assert error.failure_kind == "rate_limit"
    assert error.retryable is True
    assert error.status_code == 429
    assert error.retry_after_seconds == 12


def test_rate_limit_cooldown_short_circuits_later_requests() -> None:
    client = object.__new__(NvidiaSecurityClient)
    client._rate_limit_cooldown_until = 0.0
    client._runtime_events = []
    client._runtime_metrics = {}

    client._record_rate_limit_if_needed(
        ExternalAIServiceError(
            "rate limited",
            provider="nvidia",
            retryable=True,
            status_code=429,
            failure_kind="rate_limit",
            retry_after_seconds=10,
        )
    )

    target = _ProviderTarget(
        provider_name="nvidia",
        base_url="https://integrate.api.nvidia.com/v1",
        api_keys=("test-key",),
        timeout_seconds=30.0,
        model="test-model",
    )

    with pytest.raises(ExternalAIServiceError) as exc_info:
        client._raise_if_rate_limited(target)

    assert exc_info.value.failure_kind == "rate_limit"
    assert exc_info.value.status_code == 429
    assert client.snapshot_runtime_metrics()["rate_limit_short_circuits"] == 1
