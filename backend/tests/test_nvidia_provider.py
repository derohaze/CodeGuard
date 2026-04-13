import os
import sys
import unittest
from pathlib import Path

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
        ):
            os.environ.pop(key, None)
        get_settings.cache_clear()

    def test_settings_parse_nvidia_provider_fields(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        os.environ["NVIDIA_BASE_URL"] = "https://integrate.api.nvidia.com/v1"
        os.environ["NVIDIA_MODEL"] = "openai/gpt-oss-120b"
        os.environ["NVIDIA_SMALL_MODEL"] = "openai/gpt-oss-20b"
        os.environ["NVIDIA_LARGE_MODEL"] = "google/gemma-4-31b-it"
        os.environ["NVIDIA_ENABLE_THINKING"] = "false"
        get_settings.cache_clear()

        settings = get_settings()

        self.assertEqual(settings.nvidia_api_key, "test-key")
        self.assertEqual(settings.nvidia_small_model, "openai/gpt-oss-20b")
        self.assertEqual(settings.nvidia_large_model, "google/gemma-4-31b-it")
        self.assertFalse(settings.nvidia_enable_thinking)

    def test_factory_builds_nvidia_client_when_key_present(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        os.environ["NVIDIA_SMALL_MODEL"] = "openai/gpt-oss-20b"
        os.environ["NVIDIA_LARGE_MODEL"] = "openai/gpt-oss-120b"
        get_settings.cache_clear()

        client = _build_provider("nvidia", get_settings())

        self.assertIsInstance(client, NvidiaSecurityClient)
        self.assertEqual(client.provider_name, "nvidia")
        self.assertEqual(client.model_router.route("repository_map"), "openai/gpt-oss-20b")
        self.assertEqual(client.model_router.route("finding_validate"), "openai/gpt-oss-120b")

    def test_build_ai_client_rejects_non_nvidia_provider_order(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        os.environ["AI_PROVIDER_ORDER"] = "other,nvidia"
        get_settings.cache_clear()

        with self.assertRaises(RuntimeError):
            build_ai_client()

    def test_build_ai_client_returns_nvidia_when_order_is_supported(self) -> None:
        os.environ["NVIDIA_API_KEY"] = "test-key"
        os.environ["AI_PROVIDER_ORDER"] = "nvidia"
        get_settings.cache_clear()

        client = build_ai_client()

        self.assertIsInstance(client, NvidiaSecurityClient)


if __name__ == "__main__":
    unittest.main()
