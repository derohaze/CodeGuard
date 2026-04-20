import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.infrastructure.ai.nvidia_security_client import NvidiaSecurityClient
from app.infrastructure.ai.provider_factory import _build_provider, build_ai_client


class NvidiaProviderTests(unittest.TestCase):
    def tearDown(self) -> None:
        for key in (
            "NVIDIA_API_KEY",
            "NVIDIA_API_KEYS",
            "NVIDIA_BASE_URL",
            "NVIDIA_MODEL",
            "NVIDIA_SMALL_MODEL",
            "NVIDIA_LARGE_MODEL",
            "NVIDIA_OVERFLOW_MODEL",
            "NVIDIA_TIMEOUT_SECONDS",
            "NVIDIA_RETRY_ATTEMPTS",
            "NVIDIA_RETRY_BACKOFF_SECONDS",
            "NVIDIA_ENABLE_THINKING",
            "NVIDIA_DETECTION_MODEL",
            "NVIDIA_EXPLAIN_MODEL",
            "NVIDIA_FIX_MODEL",
            "NVIDIA_VALIDATION_MODEL",
            "NVIDIA_PENETRATION_MODEL",
            "AI_SMALL_PROVIDER",
            "AI_SMALL_MODEL",
            "AI_LARGE_PROVIDER",
            "AI_LARGE_MODEL",
            "AI_PROVIDER_ORDER",
            "BUILDER_CHAT_API_KEY",
            "BUILDER_CHAT_BASE_URL",
            "BUILDER_CHAT_MODEL",
            "BUILDER_CHAT_TIMEOUT_SECONDS",
            "PENETRATION_SANDBOX_ENABLED",
            "PENETRATION_SANDBOX_MAX_FILES",
            "PENETRATION_SANDBOX_MAX_TOTAL_MB",
        ):
            os.environ.pop(key, None)
        get_settings.cache_clear()

    def test_settings_parse_nvidia_key_pool_and_task_models(self) -> None:
        os.environ["NVIDIA_API_KEYS"] = "key-a,key-b"
        os.environ["NVIDIA_EXPLAIN_MODEL"] = "openai/gpt-oss-120b"
        os.environ["NVIDIA_FIX_MODEL"] = "z-ai/glm-5.1"
        os.environ["NVIDIA_VALIDATION_MODEL"] = "openai/gpt-oss-120b"
        os.environ["NVIDIA_PENETRATION_MODEL"] = "z-ai/glm-5.1"
        get_settings.cache_clear()

        settings = get_settings()

        self.assertEqual(settings.nvidia_api_keys, ["key-a", "key-b"])
        self.assertEqual(settings.nvidia_explain_model, "openai/gpt-oss-120b")
        self.assertEqual(settings.nvidia_fix_model, "z-ai/glm-5.1")
        self.assertEqual(settings.nvidia_validation_model, "openai/gpt-oss-120b")
        self.assertEqual(settings.nvidia_penetration_model, "z-ai/glm-5.1")

    def test_factory_builds_nvidia_client_with_task_specific_model_routing(self) -> None:
        os.environ["NVIDIA_API_KEYS"] = "key-a,key-b"
        os.environ["NVIDIA_MODEL"] = "z-ai/glm-5.1"
        os.environ["NVIDIA_SMALL_MODEL"] = "openai/gpt-oss-20b"
        os.environ["NVIDIA_LARGE_MODEL"] = "z-ai/glm-5.1"
        os.environ["NVIDIA_DETECTION_MODEL"] = "z-ai/glm-5.1"
        os.environ["NVIDIA_EXPLAIN_MODEL"] = "openai/gpt-oss-120b"
        os.environ["NVIDIA_FIX_MODEL"] = "z-ai/glm-5.1"
        os.environ["NVIDIA_VALIDATION_MODEL"] = "openai/gpt-oss-120b"
        os.environ["NVIDIA_PENETRATION_MODEL"] = "z-ai/glm-5.1"
        get_settings.cache_clear()

        client = _build_provider("nvidia", get_settings())

        self.assertIsInstance(client, NvidiaSecurityClient)
        self.assertEqual(client.provider_name, "nvidia")
        self.assertEqual(client.model_router.route("repository_map"), "z-ai/glm-5.1")
        self.assertEqual(client.model_router.route("explain"), "openai/gpt-oss-120b")
        self.assertEqual(client.model_router.route("fix_draft"), "z-ai/glm-5.1")
        self.assertEqual(client.model_router.route("fix_validate"), "openai/gpt-oss-120b")
        self.assertEqual(client.model_router.route("penetration_test"), "z-ai/glm-5.1")
        self.assertEqual(client._target_for_task("fix_validate").provider_name, "nvidia")

    def test_build_ai_client_rejects_non_nvidia_provider_order(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        os.environ["AI_PROVIDER_ORDER"] = "other,security"
        get_settings.cache_clear()

        with self.assertRaises(RuntimeError):
            build_ai_client()

    def test_build_ai_client_returns_nvidia_when_order_is_supported(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        os.environ["AI_PROVIDER_ORDER"] = "security"
        get_settings.cache_clear()

        client = build_ai_client()

        self.assertIsInstance(client, NvidiaSecurityClient)

    def test_chat_json_falls_back_to_non_strict_json_retry(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        get_settings.cache_clear()

        client = NvidiaSecurityClient()
        client._chat_text = AsyncMock(
            side_effect=[
                "not-json",
                "```json\n{\"findings\":[],\"review_note\":\"ok\"}\n```",
            ]
        )

        parsed = self._run_async(
            client._chat_json(
                task_name="finding_validate",
                max_tokens=512,
                messages=[{"role": "user", "content": "payload"}],
            )
        )

        self.assertEqual(parsed["review_note"], "ok")
        self.assertEqual(client._chat_text.await_count, 2)

    def test_chat_json_repairs_non_json_responses_before_failing(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        get_settings.cache_clear()

        client = NvidiaSecurityClient()
        client._chat_text = AsyncMock(
            side_effect=[
                "validator output without json",
                "still prose only",
                "no fenced json here either",
                "{\"review_note\":\"repaired\",\"findings\":[]}",
            ]
        )

        parsed = self._run_async(
            client._chat_json(
                task_name="finding_validate",
                max_tokens=512,
                messages=[{"role": "user", "content": "payload"}],
            )
        )

        self.assertEqual(parsed["review_note"], "repaired")
        self.assertEqual(client._chat_text.await_count, 4)

    def test_chat_text_retries_with_next_nvidia_key_after_auth_failure(self) -> None:
        os.environ["NVIDIA_API_KEYS"] = "key-a,key-b"
        get_settings.cache_clear()

        client = NvidiaSecurityClient()

        async def run():
            import httpx

            responses = [
                httpx.Response(
                    401,
                    request=httpx.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions"),
                    json={"error": {"message": "invalid key"}},
                ),
                httpx.Response(
                    200,
                    request=httpx.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions"),
                    json={"choices": [{"message": {"content": "{\"review_note\":\"ok\"}"}}]},
                ),
            ]
            seen_auth_headers: list[str] = []

            class _FakeClient:
                def __init__(self, timeout=None):
                    self.timeout = timeout

                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    return False

                async def post(self, url, json=None, headers=None):
                    seen_auth_headers.append(str(headers.get("Authorization")))
                    response = responses.pop(0)
                    return response

            original_client = httpx.AsyncClient
            httpx.AsyncClient = _FakeClient
            try:
                content = await client._chat_text(
                    task_name="repository_map",
                    max_tokens=256,
                    messages=[{"role": "user", "content": "payload"}],
                    expect_json=False,
                )
            finally:
                httpx.AsyncClient = original_client

            return content, seen_auth_headers

        content, seen_auth_headers = self._run_async(run())
        self.assertIn("\"review_note\":\"ok\"", content)
        self.assertEqual(seen_auth_headers, ["Bearer key-a", "Bearer key-b"])

    def test_chat_text_extracts_function_tool_arguments(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        get_settings.cache_clear()

        client = NvidiaSecurityClient()

        async def run():
            import httpx

            body = {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "arguments": "{\"review_note\":\"ok\",\"findings\":[]}",
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

            request = httpx.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions")
            response = httpx.Response(200, request=request, json=body)

            class _FakeClient:
                def __init__(self, timeout=None):
                    self.timeout = timeout

                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    return False

                async def post(self, url, json=None, headers=None):
                    return response

            original_client = httpx.AsyncClient
            httpx.AsyncClient = _FakeClient
            try:
                return await client._chat_text(
                    task_name="repository_map",
                    max_tokens=256,
                    messages=[{"role": "user", "content": "payload"}],
                    expect_json=False,
                )
            finally:
                httpx.AsyncClient = original_client

        content = self._run_async(run())
        self.assertIn("\"review_note\":\"ok\"", content)

    def test_chat_text_retries_single_key_across_retry_rounds(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        os.environ["NVIDIA_RETRY_ATTEMPTS"] = "2"
        os.environ["NVIDIA_RETRY_BACKOFF_SECONDS"] = "0"
        get_settings.cache_clear()

        client = NvidiaSecurityClient()

        async def run():
            import httpx

            request = httpx.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions")
            response = httpx.Response(200, request=request, json={"choices": [{"message": {"content": "{\"review_note\":\"ok\"}"}}]})
            state = {"calls": 0}

            class _FakeClient:
                def __init__(self, timeout=None):
                    self.timeout = timeout

                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    return False

                async def post(self, url, json=None, headers=None):
                    state["calls"] += 1
                    if state["calls"] == 1:
                        raise httpx.ReadTimeout("timeout", request=request)
                    return response

            original_client = httpx.AsyncClient
            httpx.AsyncClient = _FakeClient
            try:
                content = await client._chat_text(
                    task_name="repository_map",
                    max_tokens=256,
                    messages=[{"role": "user", "content": "payload"}],
                    expect_json=False,
                )
            finally:
                httpx.AsyncClient = original_client
            return content, state["calls"]

        content, calls = self._run_async(run())
        self.assertIn("\"review_note\":\"ok\"", content)
        self.assertEqual(calls, 2)

    def test_run_penetration_test_uses_finding_confidence_when_benchmark_confidence_is_missing(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        get_settings.cache_clear()

        client = NvidiaSecurityClient()
        client._chat_json = AsyncMock(
            return_value={
                "review_note": "ok",
                "executive_summary": "summary",
                "attack_chains": [],
                "reproduction_plan": [],
                "analysis_limitations": [],
                "next_steps": [],
                "benchmark": {
                    "findings_covered": 2,
                    "paths_exercised": 1,
                    "confidence_average": 0,
                    "benchmark_summary": "",
                },
                "finding_overrides": [],
            }
        )

        report = self._run_async(
            client.run_penetration_test(
                {
                    "project_name": "repo",
                    "source_path": "D:/repo",
                    "preset": "balanced",
                    "scan_mode": "deep",
                    "repository_profile": {},
                    "repository_map": {},
                    "findings": [
                        {"file": "a.py", "line": 10, "title": "A", "confidence": 90},
                        {"file": "b.py", "line": 20, "title": "B", "confidence": 70},
                    ],
                }
            )
        )

        self.assertEqual(report["benchmark"]["confidence_average"], 80)
        self.assertTrue(report["benchmark"]["benchmark_summary"])

    def test_run_penetration_test_includes_sandbox_metadata_in_prompt(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        get_settings.cache_clear()

        client = NvidiaSecurityClient()
        client._chat_json = AsyncMock(
            return_value={
                "review_note": "ok",
                "executive_summary": "summary",
                "attack_chains": [],
                "reproduction_plan": [],
                "analysis_limitations": [],
                "next_steps": [],
                "benchmark": {},
                "finding_overrides": [],
            }
        )

        self._run_async(
            client.run_penetration_test(
                {
                    "project_name": "repo",
                    "source_path": "D:/repo",
                    "preset": "balanced",
                    "scan_mode": "deep",
                    "repository_profile": {},
                    "repository_map": {},
                    "sandbox": {"enabled": True, "workspace_root": "D:/artifacts/penetration_sandboxes/scan/workspace"},
                    "findings": [{"file": "a.py", "line": 10, "title": "A", "confidence": 90}],
                }
            )
        )

        call_kwargs = client._chat_json.await_args.kwargs
        messages = call_kwargs["messages"]
        self.assertIn("Sandbox JSON:", messages[1]["content"])

    def test_summarize_verdict_returns_analysis_brief(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        get_settings.cache_clear()

        client = NvidiaSecurityClient()
        client._chat_json = AsyncMock(
            return_value={
                "review_note": "ok",
                "repository_summary": "repo",
                "coverage_summary": "coverage",
                "score_explanation": "score meaning",
                "potential_risks": ["risk"],
                "security_observations": ["observation"],
                "analysis_limitations": ["limitation"],
                "attack_thinking": ["probe"],
                "next_steps": ["step"],
            }
        )

        summary = self._run_async(
            client.summarize_verdict(
                project_name="repo",
                source_path="D:/repo",
                repository_profile={},
                repository_map={},
                findings=[],
                security_score=90,
                preset="balanced",
            )
        )

        self.assertEqual(summary["analysis_brief"]["score_explanation"], "score meaning")
        self.assertEqual(summary["analysis_brief"]["potential_risks"], ["risk"])

    def _run_async(self, awaitable):
        import asyncio

        return asyncio.run(awaitable)


if __name__ == "__main__":
    unittest.main()
