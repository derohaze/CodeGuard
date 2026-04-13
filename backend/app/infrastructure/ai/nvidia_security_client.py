from __future__ import annotations

import json
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
    normalize_remediation_payload,
    normalize_priority_path,
)
from app.infrastructure.ai.orchestration.model_router import ModelRouter
from app.infrastructure.ai.prompt_loader import load_prompt_pack


class NvidiaSecurityClient(SecurityAnalysisAIClient):
    def __init__(self) -> None:
        settings = get_settings()
        self.provider_name = "nvidia"
        self.api_key = settings.nvidia_api_key
        self.base_url = settings.nvidia_base_url.rstrip("/")
        self.small_model = settings.nvidia_small_model or settings.nvidia_model
        self.large_model = settings.nvidia_large_model or settings.nvidia_model
        self.model_router = ModelRouter(
            small_model=self.small_model,
            large_model=self.large_model,
            overflow_model=settings.nvidia_overflow_model,
        )
        self.enable_thinking = settings.nvidia_enable_thinking

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
        token_budgets = [max_tokens]
        expanded_budget = min(max(max_tokens * 2, 1536), 4096)
        if expanded_budget > max_tokens:
            token_budgets.append(expanded_budget)

        for token_budget in token_budgets:
            content = await self._chat_text(task_name=task_name, max_tokens=token_budget, messages=messages, expect_json=True)
            parsed = extract_json(content)
            if parsed:
                return parsed

        raise ExternalAIServiceError(
            "NVIDIA returned a completion without JSON content for this task.",
            provider="nvidia",
            retryable=True,
            failure_kind="output_format",
        )

    async def _chat_text(self, *, task_name: str, max_tokens: int, messages: list[dict], expect_json: bool = False) -> str:
        payload = {
            "model": self.model_router.route(task_name),
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.02,
            "top_p": 1,
            "stream": False,
        }
        if expect_json:
            payload["response_format"] = {"type": "json_object"}
        elif self.enable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": True}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        url = f"{self.base_url}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                body = response.json()
        except httpx.TimeoutException as exc:
            raise ExternalAIServiceError(
                "NVIDIA timed out while processing the request. Retry shortly.",
                provider="nvidia",
                retryable=True,
                failure_kind="timeout",
            ) from exc
        except httpx.ConnectError as exc:
            raise ExternalAIServiceError(
                "CodeGuard could not reach NVIDIA. Check network access and retry.",
                provider="nvidia",
                retryable=True,
                failure_kind="connection",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise _map_nvidia_http_error(exc.response) from exc
        except httpx.HTTPError as exc:
            raise ExternalAIServiceError(
                "NVIDIA could not complete the request because of an upstream runtime failure.",
                provider="nvidia",
                retryable=True,
                failure_kind="runtime",
            ) from exc

        choices = body.get("choices", [])
        if not choices:
            raise ExternalAIServiceError("NVIDIA returned no completion choices.", provider="nvidia", retryable=True)
        message = choices[0].get("message", {})
        content = _coerce_message_text(message.get("content"))
        if content:
            return content
        reasoning = _coerce_message_text(message.get("reasoning_content"))
        if reasoning:
            return reasoning
        raise ExternalAIServiceError(
            "NVIDIA returned a completion without usable content.",
            provider="nvidia",
            retryable=False,
            failure_kind="output_format",
        )


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


def _map_nvidia_http_error(response: httpx.Response) -> ExternalAIServiceError:
    try:
        body = response.json()
    except ValueError:
        body = None
    message = _extract_provider_message(body)
    normalized = message.lower()
    status_code = response.status_code

    if status_code == 429:
        return ExternalAIServiceError(
            "NVIDIA rate limits were reached while processing the request. Retry in a moment.",
            provider="nvidia",
            retryable=True,
            status_code=status_code,
            failure_kind="rate_limit",
        )
    if status_code == 413 or "request too large" in normalized or "max tokens" in normalized or "context" in normalized:
        return ExternalAIServiceError(
            f"NVIDIA rejected the request size: {message}",
            provider="nvidia",
            retryable=True,
            status_code=status_code,
            failure_kind="payload_too_large",
        )
    if status_code in {502, 503, 504}:
        return ExternalAIServiceError(
            f"NVIDIA returned an upstream gateway error ({status_code}). Retry the request.",
            provider="nvidia",
            retryable=True,
            status_code=status_code,
            failure_kind="gateway",
        )
    if status_code >= 500:
        return ExternalAIServiceError(
            f"NVIDIA returned an unexpected upstream error ({status_code}). Retry the request.",
            provider="nvidia",
            retryable=True,
            status_code=status_code,
            failure_kind="upstream",
        )
    return ExternalAIServiceError(
        f"NVIDIA rejected the remediation or scan request: {message}",
        provider="nvidia",
        retryable=False,
        status_code=status_code,
        failure_kind="request_rejected",
    )
