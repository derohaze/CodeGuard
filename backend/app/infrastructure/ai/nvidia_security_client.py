from __future__ import annotations

import json
from dataclasses import dataclass
import logging
from textwrap import shorten

import httpx

from app.core.config import get_settings
from app.core.exceptions import ExternalAIServiceError
from app.domain.services.ai_client import SecurityAnalysisAIClient
from app.infrastructure.ai.client_utils import (
    compact_findings,
    extract_json,
    extract_review_payload,
    json_for_task_prompt,
    normalize_analysis_brief,
    normalize_remediation_payload,
    normalize_priority_path,
)
from app.infrastructure.ai.orchestration.model_router import ModelRouter
from app.infrastructure.ai.prompt_loader import load_prompt_pack

logger = logging.getLogger("aegix.ai")


@dataclass(frozen=True, slots=True)
class _ProviderTarget:
    provider_name: str
    base_url: str
    api_key: str | None
    timeout_seconds: float
    model: str
    enable_thinking: bool = False


_SUPPORTED_TARGET_PROVIDERS = frozenset({"nvidia", "routing_run"})
_DEPTH_TASKS = frozenset({"explain", "fix_validate", "patch_validate", "final_patch", "verdict", "finding_validate"})


class NvidiaSecurityClient(SecurityAnalysisAIClient):
    def __init__(self) -> None:
        settings = get_settings()
        self.provider_name = "nvidia"
        self.api_key = settings.nvidia_api_key
        self.base_url = settings.nvidia_base_url.rstrip("/")
        self._small_target = _resolve_provider_target(settings, tier="small")
        self._large_target = _resolve_provider_target(settings, tier="large", fallback=self._small_target)
        self.small_model = self._small_target.model
        self.large_model = self._large_target.model
        self.model_router = ModelRouter(
            small_model=self.small_model,
            large_model=self.large_model,
            overflow_model=settings.nvidia_overflow_model,
        )
        self.enable_thinking = settings.nvidia_enable_thinking

    @staticmethod
    def is_configured(settings) -> bool:
        try:
            _resolve_provider_target(settings, tier="small")
        except RuntimeError:
            return False
        return True

    async def map_repository(self, project_name: str, source_path: str, repository_profile: dict, repository_artifacts: dict, preset: str) -> dict:
        parsed = await self._chat_json(
            task_name="repository_map",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": load_prompt_pack("repository_mapper.md")},
                {
                    "role": "user",
                    "content": (
                        f"Project: {project_name}\n"
                        f"Source: {source_path}\n"
                        f"Preset: {preset}\n"
                        f"Repository profile JSON: {json_for_task_prompt('repository_map', 'repository_profile', repository_profile, max_chars=1800)}\n"
                        f"Repository artifacts JSON: {json_for_task_prompt('repository_map', 'repository_artifacts', repository_artifacts, max_chars=2800)}"
                    ),
                },
            ],
        )
        return {
            "review_note": shorten(str(parsed.get("review_note", "")), width=180, placeholder="..."),
            "repository_summary": shorten(str(parsed.get("repository_summary", "")), width=260, placeholder="..."),
            "coverage_note": shorten(str(parsed.get("coverage_note", "")), width=220, placeholder="..."),
            "trust_boundaries": [str(item) for item in parsed.get("trust_boundaries", []) if str(item).strip()][:10],
            "priority_paths": [normalize_priority_path(item) for item in parsed.get("priority_paths", []) if isinstance(item, dict)],
        }

    async def review_paths(self, project_name: str, source_path: str, repository_profile: dict, repository_map: dict, work_items: list[dict[str, str]], batch_index: int, total_batches: int, preset: str) -> dict:
        if not work_items:
            return {"review_note": "No prioritized work items reached the path reviewer.", "repository_summary": "", "findings": []}
        parsed = await self._chat_json(
            task_name="path_review",
            max_tokens=1536,
            messages=[
                {"role": "system", "content": load_prompt_pack("path_reviewer.md")},
                {
                    "role": "user",
                    "content": (
                        f"Project: {project_name}\n"
                        f"Source: {source_path}\n"
                        f"Preset: {preset}\n"
                        f"Batch: {batch_index}/{total_batches}\n"
                        f"Repository profile JSON: {json_for_task_prompt('path_review', 'repository_profile', repository_profile, max_chars=1200)}\n"
                        f"Repository map JSON: {json_for_task_prompt('path_review', 'repository_map', repository_map, max_chars=1800)}\n"
                        f"Prioritized work items JSON: {json_for_task_prompt('path_review', 'work_items', work_items, max_chars=2600)}"
                    ),
                },
            ],
        )
        return extract_review_payload(json.dumps(parsed, ensure_ascii=False))

    async def validate_findings(self, project_name: str, source_path: str, repository_profile: dict, repository_map: dict, findings: list[dict], preset: str) -> dict:
        if not findings:
            return {"review_note": "The validator did not receive any candidate findings.", "safe_summary": "No confirmed high-confidence issue was found in the reviewed scope.", "findings": []}
        parsed = await self._chat_json(
            task_name="finding_validate",
            max_tokens=1536,
            messages=[
                {"role": "system", "content": load_prompt_pack("finding_validator.md")},
                {
                    "role": "user",
                    "content": (
                        f"Project: {project_name}\n"
                        f"Source: {source_path}\n"
                        f"Preset: {preset}\n"
                        f"Repository profile JSON: {json_for_task_prompt('finding_validate', 'repository_profile', repository_profile, max_chars=1200)}\n"
                        f"Repository map JSON: {json_for_task_prompt('finding_validate', 'repository_map', repository_map, max_chars=1800)}\n"
                        f"Potential findings JSON: {json_for_task_prompt('finding_validate', 'findings', compact_findings(findings, limit=18), max_chars=2200)}"
                    ),
                },
            ],
        )
        parsed = extract_review_payload(json.dumps(parsed, ensure_ascii=False))
        return {
            "review_note": parsed["review_note"],
            "safe_summary": shorten(str(parsed.get("safe_summary", "")), width=220, placeholder="..."),
            "findings": parsed["findings"],
        }

    async def summarize_verdict(self, project_name: str, source_path: str, repository_profile: dict, repository_map: dict, findings: list[dict], security_score: int | None, preset: str) -> dict:
        parsed = await self._chat_json(
            task_name="verdict",
            max_tokens=768,
            messages=[
                {"role": "system", "content": load_prompt_pack("verdict_analyst.md")},
                {
                    "role": "user",
                    "content": (
                        f"Project: {project_name}\n"
                        f"Source: {source_path}\n"
                        f"Preset: {preset}\n"
                        f"Security score: {security_score}\n"
                        f"Repository profile JSON: {json_for_task_prompt('verdict', 'repository_profile', repository_profile, max_chars=1000)}\n"
                        f"Repository map JSON: {json_for_task_prompt('verdict', 'repository_map', repository_map, max_chars=1600)}\n"
                        f"Confirmed findings JSON: {json_for_task_prompt('verdict', 'findings', compact_findings(findings, limit=16), max_chars=1800)}"
                    ),
                },
            ],
        )
        return {
            "review_note": shorten(str(parsed.get("review_note", "")), width=180, placeholder="..."),
            "repository_summary": shorten(str(parsed.get("repository_summary", "")), width=260, placeholder="..."),
            "coverage_summary": shorten(str(parsed.get("coverage_summary", "")), width=220, placeholder="..."),
            "analysis_brief": normalize_analysis_brief(parsed),
        }

    async def explain_finding(self, remediation_context: dict) -> dict:
        parsed = await self._chat_json(
            task_name="explain",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": load_prompt_pack("explain_prompt.md")},
                {"role": "user", "content": f"Remediation context JSON: {json_for_task_prompt('explain', 'remediation_context', remediation_context, max_chars=2600)}"},
            ],
        )
        return {
            "summary": shorten(str(parsed.get("summary", "")), width=240, placeholder="..."),
            "exploit_scenario": shorten(str(parsed.get("exploit_scenario", "")), width=560, placeholder="..."),
            "request_example": str(parsed.get("request_example", "")),
            "payload_example": str(parsed.get("payload_example", "")),
            "attack_steps": [str(item) for item in parsed.get("attack_steps", []) if str(item).strip()][:6],
            "entry_point": shorten(str(parsed.get("entry_point", "")), width=180, placeholder="..."),
            "execution_path": shorten(str(parsed.get("execution_path", "")), width=240, placeholder="..."),
            "sink": shorten(str(parsed.get("sink", "")), width=140, placeholder="..."),
            "impact": shorten(str(parsed.get("impact", "")), width=220, placeholder="..."),
        }

    async def draft_fix_strategies(self, remediation_context: dict, mode: str) -> dict:
        parsed = await self._chat_json(
            task_name="fix_draft",
            max_tokens=1536,
            messages=[
                {"role": "system", "content": load_prompt_pack("fix_prompt.md")},
                {"role": "user", "content": f"Mode: {mode}\nRemediation context JSON: {json_for_task_prompt('fix_draft', 'remediation_context', remediation_context, max_chars=2800)}"},
            ],
        )
        return normalize_remediation_payload(parsed)

    async def validate_remediation(self, remediation_context: dict, remediation_draft: dict, mode: str) -> dict:
        parsed = await self._chat_json(
            task_name="fix_validate",
            max_tokens=1536,
            messages=[
                {"role": "system", "content": load_prompt_pack("fix_validator_prompt.md")},
                {
                    "role": "user",
                    "content": (
                        f"Mode: {mode}\n"
                        f"Remediation context JSON: {json_for_task_prompt('fix_validate', 'remediation_context', remediation_context, max_chars=2200)}\n"
                        f"Draft remediation JSON: {json_for_task_prompt('fix_validate', 'remediation_draft', remediation_draft, max_chars=2200)}"
                    ),
                },
            ],
        )
        return normalize_remediation_payload(
            parsed,
            fallback_review_summary=str(remediation_draft.get("review_summary", "")),
            fallback_recommended_strategy_id=remediation_draft.get("recommended_strategy_id"),
            fallback_strategies=remediation_draft.get("strategies", []),
            fallback_patch=remediation_draft.get("patch", {}),
        )

    async def _chat_json(self, *, task_name: str, max_tokens: int, messages: list[dict]) -> dict:
        target = self._target_for_task(task_name)
        token_budgets = [max_tokens]
        expanded_budget = min(max(max_tokens * 2, 1536), 4096)
        if expanded_budget > max_tokens:
            token_budgets.append(expanded_budget)
        raw_responses: list[str] = []

        for token_budget in token_budgets:
            content = await self._chat_text(
                task_name=task_name,
                max_tokens=token_budget,
                messages=_force_json_only_messages(messages) if target.provider_name == "routing_run" else messages,
                expect_json=target.provider_name != "routing_run",
            )
            if content:
                raw_responses.append(content)
            parsed = extract_json(content)
            if parsed:
                return parsed

        # Some OpenAI-compatible providers ignore response_format and return fenced or prose-wrapped JSON.
        fallback_messages = _force_json_only_messages(messages)
        fallback_budget = min(max(max_tokens * 2, 1536), 4096)
        content = await self._chat_text(task_name=task_name, max_tokens=fallback_budget, messages=fallback_messages, expect_json=False)
        if content:
            raw_responses.append(content)
        parsed = extract_json(content)
        if parsed:
            return parsed

        repaired = await self._repair_json_response(task_name=task_name, messages=messages, raw_responses=raw_responses)
        if repaired:
            return repaired

        raise ExternalAIServiceError(
            "The configured AI provider returned a completion without JSON content for this task.",
            provider=self._target_for_task(task_name).provider_name,
            retryable=True,
            failure_kind="output_format",
        )

    async def _chat_text(self, *, task_name: str, max_tokens: int, messages: list[dict], expect_json: bool = False, target: _ProviderTarget | None = None) -> str:
        target = target or self._target_for_task(task_name)
        payload = {
            "model": target.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.02,
            "top_p": 1,
            "stream": False,
        }
        if expect_json:
            payload["response_format"] = {"type": "json_object"}
        elif target.enable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": True}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {target.api_key}",
        }
        url = _chat_completions_url(target.base_url)
        logger.info(
            "AI request dispatch | task=%s provider=%s model=%s url=%s expect_json=%s max_tokens=%s",
            task_name,
            target.provider_name,
            target.model,
            url,
            expect_json,
            max_tokens,
        )
        try:
            async with httpx.AsyncClient(timeout=target.timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                body = response.json()
        except httpx.TimeoutException as exc:
            raise ExternalAIServiceError(
                _provider_timeout_message(target.provider_name),
                provider=target.provider_name,
                retryable=True,
                failure_kind="timeout",
            ) from exc
        except httpx.ConnectError as exc:
            raise ExternalAIServiceError(
                _provider_connection_message(target.provider_name),
                provider=target.provider_name,
                retryable=True,
                failure_kind="connection",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise _map_provider_http_error(target.provider_name, exc.response) from exc
        except httpx.HTTPError as exc:
            raise ExternalAIServiceError(
                _provider_runtime_message(target.provider_name),
                provider=target.provider_name,
                retryable=True,
                failure_kind="runtime",
            ) from exc

        choices = body.get("choices", [])
        if not choices:
            raise ExternalAIServiceError(
                "The configured AI provider returned no completion choices.",
                provider=target.provider_name,
                retryable=True,
                failure_kind="output_format",
            )
        content = _extract_completion_text(body)
        if content:
            return content
        raise ExternalAIServiceError(
            _provider_output_message(target.provider_name),
            provider=target.provider_name,
            retryable=False,
            failure_kind="output_format",
        )

    def _target_for_task(self, task_name: str) -> _ProviderTarget:
        if task_name.strip().lower() in _DEPTH_TASKS:
            return self._large_target
        return self._small_target

    async def _repair_json_response(self, *, task_name: str, messages: list[dict], raw_responses: list[str]) -> dict:
        if not raw_responses:
            return {}

        repair_target = self._small_target
        repair_messages = _build_json_repair_messages(task_name=task_name, messages=messages, raw_response=raw_responses[-1])
        repair_budget = min(max(1024, len(raw_responses[-1]) // 2), 2048)

        content = await self._chat_text(
            task_name=f"{task_name}_json_repair",
            max_tokens=repair_budget,
            messages=repair_messages,
            expect_json=repair_target.provider_name != "routing_run",
            target=repair_target,
        )
        return extract_json(content)


def _coerce_message_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                if item.strip():
                    parts.append(item.strip())
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _force_json_only_messages(messages: list[dict]) -> list[dict]:
    forced_messages = list(messages)
    if not forced_messages:
        return forced_messages
    forced_messages[-1] = {
        **forced_messages[-1],
        "content": (
            f"{forced_messages[-1].get('content', '')}\n\n"
            "Return exactly one JSON object and nothing else. "
            "Do not use markdown fences, bullet lists, or explanatory prose. "
            "If a field has no evidence, return an empty string or empty array instead of commentary."
        ),
    }
    return forced_messages


def _build_json_repair_messages(*, task_name: str, messages: list[dict], raw_response: str) -> list[dict]:
    system_prompt = ""
    user_prompt = ""
    if messages:
        system_prompt = _message_content_as_text(messages[0].get("content"))
        user_prompt = _message_content_as_text(messages[-1].get("content"))

    return [
        {
            "role": "system",
            "content": (
                "You repair malformed AI outputs into one strict JSON object. "
                "Preserve only claims grounded in the provided raw output and task instructions. "
                "Return exactly one JSON object and nothing else."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Task: {task_name}\n"
                f"Original system instructions:\n{shorten(system_prompt, width=1800, placeholder='...')}\n\n"
                f"Original request:\n{shorten(user_prompt, width=2200, placeholder='...')}\n\n"
                f"Raw model output to repair:\n{shorten(raw_response, width=3200, placeholder='...')}"
            ),
        },
    ]


def _message_content_as_text(value) -> str:
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
        return "\n".join(parts).strip()
    return str(value or "")


def _extract_completion_text(body: dict) -> str:
    choices = body.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return ""

    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get("message", {})
    if not isinstance(message, dict):
        message = {}

    for value in (
        message.get("parsed"),
        message.get("json"),
        body.get("output"),
        body.get("output_text"),
        choice.get("text"),
        message.get("content"),
        message.get("reasoning_content"),
    ):
        text = _coerce_payload_text(value)
        if text:
            return text

    function_call = message.get("function_call")
    if isinstance(function_call, dict):
        arguments = _coerce_payload_text(function_call.get("arguments"))
        if arguments:
            return arguments

    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            function = tool_call.get("function")
            if not isinstance(function, dict):
                continue
            arguments = _coerce_payload_text(function.get("arguments"))
            if arguments:
                return arguments

    return ""


def _coerce_payload_text(value) -> str:
    if isinstance(value, dict):
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return ""
    return _coerce_message_text(value)


def _extract_provider_message(body: dict | None) -> str:
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


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _resolve_provider_target(settings, *, tier: str, fallback: _ProviderTarget | None = None) -> _ProviderTarget:
    provider_name = _resolve_provider_name(settings, tier=tier)
    if provider_name not in _SUPPORTED_TARGET_PROVIDERS:
        raise RuntimeError(f"Unsupported AI target provider '{provider_name}' for {tier} tier.")

    if provider_name == "nvidia":
        model = _resolve_nvidia_model(settings, tier=tier)
        api_key = settings.nvidia_api_key
        if not api_key:
            if fallback is not None:
                return fallback
            raise RuntimeError("NVIDIA is not configured. Set NVIDIA_API_KEY.")
        return _ProviderTarget(
            provider_name="nvidia",
            base_url=settings.nvidia_base_url.rstrip("/"),
            api_key=api_key,
            timeout_seconds=120.0,
            model=model,
            enable_thinking=settings.nvidia_enable_thinking,
        )

    model = _resolve_routing_run_model(settings, tier=tier)
    api_key = settings.builder_chat_api_key
    if not api_key:
        if fallback is not None:
            return fallback
        raise RuntimeError("routing.run is not configured. Set BUILDER_CHAT_API_KEY.")
    return _ProviderTarget(
        provider_name="routing_run",
        base_url=settings.builder_chat_base_url,
        api_key=api_key,
        timeout_seconds=settings.builder_chat_timeout_seconds,
        model=model,
        enable_thinking=False,
    )


def _resolve_provider_name(settings, *, tier: str) -> str:
    if tier == "small":
        return settings.ai_small_provider or "nvidia"

    if settings.ai_large_provider:
        return settings.ai_large_provider
    if settings.builder_chat_api_key:
        return "routing_run"
    if settings.ai_large_model:
        return settings.ai_large_provider or "nvidia"
    if settings.nvidia_large_model:
        return "nvidia"
    return settings.ai_small_provider or "nvidia"


def _resolve_nvidia_model(settings, *, tier: str) -> str:
    if tier == "small":
        return settings.ai_small_model or settings.nvidia_small_model or settings.nvidia_model
    return settings.ai_large_model or settings.nvidia_large_model or settings.nvidia_model


def _resolve_routing_run_model(settings, *, tier: str) -> str:
    if tier == "small":
        return settings.ai_small_model or settings.builder_chat_model
    return settings.ai_large_model or settings.builder_chat_model


def _provider_timeout_message(provider_name: str) -> str:
    if provider_name == "routing_run":
        return "Routing.run timed out while processing the request. Retry shortly."
    return "NVIDIA timed out while processing the request. Retry shortly."


def _provider_connection_message(provider_name: str) -> str:
    if provider_name == "routing_run":
        return "Aegix could not reach routing.run. Check network access and retry."
    return "Aegix could not reach NVIDIA. Check network access and retry."


def _provider_runtime_message(provider_name: str) -> str:
    if provider_name == "routing_run":
        return "routing.run could not complete the request because of an upstream runtime failure."
    return "NVIDIA could not complete the request because of an upstream runtime failure."


def _provider_output_message(provider_name: str) -> str:
    if provider_name == "routing_run":
        return "routing.run returned a completion without usable content."
    return "NVIDIA returned a completion without usable content."


def _map_provider_http_error(provider_name: str, response: httpx.Response) -> ExternalAIServiceError:
    try:
        body = response.json()
    except ValueError:
        body = None
    message = _extract_provider_message(body)
    normalized = message.lower()
    status_code = response.status_code
    provider_label = "routing.run" if provider_name == "routing_run" else "NVIDIA"

    if status_code == 429:
        return ExternalAIServiceError(
            f"{provider_label} rate limits were reached while processing the request. Retry in a moment.",
            provider=provider_name,
            retryable=True,
            status_code=status_code,
            failure_kind="rate_limit",
        )
    if status_code == 413 or "request too large" in normalized or "max tokens" in normalized or "context" in normalized:
        return ExternalAIServiceError(
            f"{provider_label} rejected the request size: {message}",
            provider=provider_name,
            retryable=True,
            status_code=status_code,
            failure_kind="payload_too_large",
        )
    if status_code in {502, 503, 504}:
        return ExternalAIServiceError(
            f"{provider_label} returned an upstream gateway error ({status_code}). Retry the request.",
            provider=provider_name,
            retryable=True,
            status_code=status_code,
            failure_kind="gateway",
        )
    if status_code >= 500:
        return ExternalAIServiceError(
            f"{provider_label} returned an unexpected upstream error ({status_code}). Retry the request.",
            provider=provider_name,
            retryable=True,
            status_code=status_code,
            failure_kind="upstream",
        )
    return ExternalAIServiceError(
        f"{provider_label} rejected the remediation or scan request: {message}",
        provider=provider_name,
        retryable=False,
        status_code=status_code,
        failure_kind="request_rejected",
    )
