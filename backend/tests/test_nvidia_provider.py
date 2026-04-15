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
            "NVIDIA_BASE_URL",
            "NVIDIA_MODEL",
            "NVIDIA_SMALL_MODEL",
            "NVIDIA_LARGE_MODEL",
            "NVIDIA_OVERFLOW_MODEL",
            "NVIDIA_ENABLE_THINKING",
            "AI_SMALL_PROVIDER",
            "AI_SMALL_MODEL",
            "AI_LARGE_PROVIDER",
            "AI_LARGE_MODEL",
            "AI_PROVIDER_ORDER",
            "BUILDER_CHAT_API_KEY",
            "BUILDER_CHAT_BASE_URL",
            "BUILDER_CHAT_MODEL",
            "BUILDER_CHAT_TIMEOUT_SECONDS",
        ):
            os.environ.pop(key, None)
        get_settings.cache_clear()

    def test_settings_parse_provider_routing_fields(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        os.environ["AI_SMALL_PROVIDER"] = "nvidia"
        os.environ["AI_SMALL_MODEL"] = "openai/gpt-oss-20b"
        os.environ["AI_LARGE_PROVIDER"] = "routing_run"
        os.environ["AI_LARGE_MODEL"] = "route/glm-5.1-precision"
        get_settings.cache_clear()

        settings = get_settings()

        self.assertEqual(settings.nvidia_api_key, "test-key")
        self.assertEqual(settings.ai_small_provider, "nvidia")
        self.assertEqual(settings.ai_small_model, "openai/gpt-oss-20b")
        self.assertEqual(settings.ai_large_provider, "routing_run")
        self.assertEqual(settings.ai_large_model, "route/glm-5.1-precision")

    def test_factory_builds_client_from_explicit_small_and_large_provider_routing(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        os.environ["AI_SMALL_PROVIDER"] = "nvidia"
        os.environ["AI_SMALL_MODEL"] = "openai/gpt-oss-20b"
        os.environ["AI_LARGE_PROVIDER"] = "routing_run"
        os.environ["AI_LARGE_MODEL"] = "route/glm-5.1-precision"
        os.environ["BUILDER_CHAT_API_KEY"] = "routing-run-test-key"
        os.environ["BUILDER_CHAT_BASE_URL"] = "https://api.routing.run/v1/chat/completions"
        get_settings.cache_clear()

        client = _build_provider("nvidia", get_settings())

        self.assertIsInstance(client, NvidiaSecurityClient)
        self.assertEqual(client.provider_name, "nvidia")
        self.assertEqual(client.model_router.route("repository_map"), "openai/gpt-oss-20b")
        self.assertEqual(client.model_router.route("finding_validate"), "route/glm-5.1-precision")
        self.assertEqual(client._target_for_task("repository_map").provider_name, "nvidia")
        self.assertEqual(client._target_for_task("finding_validate").provider_name, "routing_run")

    def test_client_keeps_legacy_fallback_when_large_provider_is_not_declared(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "nvidia-test-key"
        os.environ["NVIDIA_SMALL_MODEL"] = "openai/gpt-oss-20b"
        os.environ["BUILDER_CHAT_API_KEY"] = "routing-run-test-key"
        os.environ["BUILDER_CHAT_BASE_URL"] = "https://api.routing.run/v1/chat/completions"
        os.environ["BUILDER_CHAT_MODEL"] = "route/glm-5.1-precision"
        os.environ["BUILDER_CHAT_TIMEOUT_SECONDS"] = "90"
        get_settings.cache_clear()

        client = _build_provider("nvidia", get_settings())

        self.assertIsInstance(client, NvidiaSecurityClient)
        self.assertEqual(client.model_router.route("repository_map"), "openai/gpt-oss-20b")
        self.assertEqual(client.model_router.route("finding_validate"), "route/glm-5.1-precision")
        self.assertEqual(client._target_for_task("repository_map").provider_name, "nvidia")
        self.assertEqual(client._target_for_task("finding_validate").provider_name, "routing_run")

    def test_build_ai_client_can_run_with_routing_run_only_when_both_tiers_are_set(self) -> None:
        os.environ["AI_SMALL_PROVIDER"] = "routing_run"
        os.environ["AI_SMALL_MODEL"] = "route/glm-5.1-mini"
        os.environ["AI_LARGE_PROVIDER"] = "routing_run"
        os.environ["AI_LARGE_MODEL"] = "route/glm-5.1-precision"
        os.environ["BUILDER_CHAT_API_KEY"] = "routing-run-test-key"
        os.environ["BUILDER_CHAT_BASE_URL"] = "https://api.routing.run/v1/chat/completions"
        os.environ["AI_PROVIDER_ORDER"] = "security"
        get_settings.cache_clear()

        client = build_ai_client()

        self.assertIsInstance(client, NvidiaSecurityClient)
        self.assertEqual(client.model_router.route("repository_map"), "route/glm-5.1-mini")
        self.assertEqual(client.model_router.route("finding_validate"), "route/glm-5.1-precision")
        self.assertEqual(client._target_for_task("repository_map").provider_name, "routing_run")
        self.assertEqual(client._target_for_task("finding_validate").provider_name, "routing_run")

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
        client._chat_text = AsyncMock(side_effect=[
            "not-json",
            "```json\n{\"findings\":[],\"review_note\":\"ok\"}\n```",
        ])

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
        os.environ["AI_SMALL_PROVIDER"] = "nvidia"
        os.environ["NVIDIA_API_KEY"] = "test-key"
        os.environ["AI_LARGE_PROVIDER"] = "routing_run"
        os.environ["AI_LARGE_MODEL"] = "route/glm-5.1-precision"
        os.environ["BUILDER_CHAT_API_KEY"] = "routing-run-test-key"
        os.environ["BUILDER_CHAT_BASE_URL"] = "https://api.routing.run/v1/chat/completions"
        get_settings.cache_clear()

        client = NvidiaSecurityClient()
        client._chat_text = AsyncMock(side_effect=[
            "validator output without json",
            "still prose only",
            "no fenced json here either",
            "{\"review_note\":\"repaired\",\"findings\":[]}",
        ])

        parsed = self._run_async(
            client._chat_json(
                task_name="finding_validate",
                max_tokens=512,
                messages=[{"role": "user", "content": "payload"}],
            )
        )

        self.assertEqual(parsed["review_note"], "repaired")
        self.assertEqual(client._chat_text.await_count, 4)

    def test_chat_text_extracts_function_tool_arguments(self) -> None:
        os.environ["AI_SMALL_PROVIDER"] = "routing_run"
        os.environ["AI_SMALL_MODEL"] = "route/glm-5.1-mini"
        os.environ["BUILDER_CHAT_API_KEY"] = "routing-run-test-key"
        os.environ["BUILDER_CHAT_BASE_URL"] = "https://api.routing.run/v1/chat/completions"
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

            request = httpx.Request("POST", "https://api.routing.run/v1/chat/completions")
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
