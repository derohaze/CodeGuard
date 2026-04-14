from __future__ import annotations

from dataclasses import dataclass
import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import get_settings
from app.core.exceptions import ExternalAIServiceError


@dataclass(slots=True)
class BuilderProviderUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(slots=True)
class BuilderProviderReply:
    text: str
    model: str
    usage: BuilderProviderUsage | None = None


class RoutingRunBuilderProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.builder_chat_api_key
        self.base_url = settings.builder_chat_base_url
        self.model = settings.builder_chat_model
        self.timeout_seconds = settings.builder_chat_timeout_seconds
        self.temperature = settings.builder_chat_temperature
        self.max_tokens = settings.builder_chat_max_tokens

    async def generate_reply(self, messages: list[dict[str, str]]) -> BuilderProviderReply:
        if not self.api_key:
            raise ExternalAIServiceError(
                "Builder chat provider key is missing. Set BUILDER_CHAT_API_KEY in .env.",
                provider="routing_run",
                retryable=False,
                failure_kind="configuration",
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.base_url, json=payload, headers=headers)
                response.raise_for_status()
                body = response.json()
        except httpx.TimeoutException as exc:
            raise ExternalAIServiceError(
                "Builder provider timed out while generating a response.",
                provider="routing_run",
                retryable=True,
                failure_kind="timeout",
            ) from exc
        except httpx.ConnectError as exc:
            raise ExternalAIServiceError(
                "Builder provider is unreachable. Check network access and base URL.",
                provider="routing_run",
                retryable=True,
                failure_kind="connection",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            message = _extract_error_message(exc.response)
            raise ExternalAIServiceError(
                f"Builder provider rejected the request ({status_code}): {message}",
                provider="routing_run",
                retryable=status_code >= 500 or status_code == 429,
                status_code=status_code,
                failure_kind="request_rejected",
            ) from exc
        except httpx.HTTPError as exc:
            raise ExternalAIServiceError(
                "Builder provider returned an upstream runtime failure.",
                provider="routing_run",
                retryable=True,
                failure_kind="runtime",
            ) from exc

        choices = body.get("choices", [])
        if not choices:
            raise ExternalAIServiceError(
                "Builder provider returned no completion choices.",
                provider="routing_run",
                retryable=True,
                failure_kind="output_format",
            )

        message = choices[0].get("message", {})
        content = _coerce_message_content(message.get("content"))
        if not content:
            raise ExternalAIServiceError(
                "Builder provider returned empty message content.",
                provider="routing_run",
                retryable=False,
                failure_kind="output_format",
            )

        model = str(body.get("model") or self.model)
        return BuilderProviderReply(
            text=content,
            model=model,
            usage=_extract_usage_payload(body.get("usage")),
        )

    async def generate_reply_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[dict[str, object]]:
        if not self.api_key:
            raise ExternalAIServiceError(
                "Builder chat provider key is missing. Set BUILDER_CHAT_API_KEY in .env.",
                provider="routing_run",
                retryable=False,
                failure_kind="configuration",
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        seen_content = False
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream("POST", self.base_url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    async for raw_line in response.aiter_lines():
                        line = raw_line.strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data = line.removeprefix("data:").strip()
                        if data == "[DONE]":
                            break
                        if not data:
                            continue

                        chunk = json.loads(data)
                        model = str(chunk.get("model") or self.model)
                        yield {"type": "meta", "model": model}
                        usage = _extract_usage_payload(chunk.get("usage"))
                        if usage is not None:
                            yield {
                                "type": "usage",
                                "input_tokens": usage.input_tokens,
                                "output_tokens": usage.output_tokens,
                                "total_tokens": usage.total_tokens,
                            }

                        choices = chunk.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        reasoning = _coerce_reasoning_fragment(
                            delta.get("reasoning_content")
                            if "reasoning_content" in delta
                            else delta.get("reasoning")
                        )
                        if reasoning:
                            yield {"type": "reasoning", "text": reasoning}

                        content = _coerce_stream_fragment(delta.get("content"))
                        if content:
                            seen_content = True
                            yield {"type": "token", "text": content}
        except httpx.TimeoutException as exc:
            raise ExternalAIServiceError(
                "Builder provider timed out while generating a response.",
                provider="routing_run",
                retryable=True,
                failure_kind="timeout",
            ) from exc
        except httpx.ConnectError as exc:
            raise ExternalAIServiceError(
                "Builder provider is unreachable. Check network access and base URL.",
                provider="routing_run",
                retryable=True,
                failure_kind="connection",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            message = _extract_error_message(exc.response)
            raise ExternalAIServiceError(
                f"Builder provider rejected the request ({status_code}): {message}",
                provider="routing_run",
                retryable=status_code >= 500 or status_code == 429,
                status_code=status_code,
                failure_kind="request_rejected",
            ) from exc
        except httpx.HTTPError as exc:
            raise ExternalAIServiceError(
                "Builder provider returned an upstream runtime failure.",
                provider="routing_run",
                retryable=True,
                failure_kind="runtime",
            ) from exc
        except json.JSONDecodeError as exc:
            raise ExternalAIServiceError(
                "Builder provider returned malformed stream payload.",
                provider="routing_run",
                retryable=True,
                failure_kind="output_format",
            ) from exc

        if not seen_content:
            raise ExternalAIServiceError(
                "Builder provider returned empty message content.",
                provider="routing_run",
                retryable=False,
                failure_kind="output_format",
            )


def _coerce_message_content(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _coerce_stream_fragment(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _coerce_reasoning_fragment(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _extract_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text.strip() or "Unknown provider error."

    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        detail = body.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
    return "Unknown provider error."


def _extract_usage_payload(value: object) -> BuilderProviderUsage | None:
    if not isinstance(value, dict):
        return None

    input_tokens = _coerce_usage_int(value.get("input_tokens"))
    if input_tokens is None:
        input_tokens = _coerce_usage_int(value.get("prompt_tokens"))

    output_tokens = _coerce_usage_int(value.get("output_tokens"))
    if output_tokens is None:
        output_tokens = _coerce_usage_int(value.get("completion_tokens"))

    total_tokens = _coerce_usage_int(value.get("total_tokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None

    return BuilderProviderUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _coerce_usage_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float):
        return max(int(value), 0)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return max(int(float(stripped)), 0)
        except ValueError:
            return None
    return None
