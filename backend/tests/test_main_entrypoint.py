import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT_PATH = BACKEND_ROOT / "main.py"


def _load_entrypoint_module():
    spec = importlib.util.spec_from_file_location("codeguard_backend_entrypoint", ENTRYPOINT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["codeguard_backend_entrypoint"] = module
    spec.loader.exec_module(module)
    return module


class BackendEntrypointTests(unittest.TestCase):
    def test_reload_stays_enabled_for_in_process_queue(self):
        module = _load_entrypoint_module()

        with patch.object(module, "get_settings", return_value=type("S", (), {"app_env": "development", "queue_backend": "in_process", "auto_start_queue_worker": True, "api_workers": 1})()):
            self.assertTrue(module._should_enable_reload())
            self.assertFalse(module._should_start_embedded_worker())

    def test_reload_is_disabled_when_main_autostarts_arq_worker(self):
        module = _load_entrypoint_module()

        with patch.object(module, "get_settings", return_value=type("S", (), {"app_env": "development", "queue_backend": "arq", "auto_start_queue_worker": True, "api_workers": 1})()):
            self.assertFalse(module._should_enable_reload())
            self.assertTrue(module._should_start_embedded_worker())

    def test_reload_is_disabled_when_api_workers_exceed_one(self):
        module = _load_entrypoint_module()

        with patch.object(module, "get_settings", return_value=type("S", (), {"app_env": "development", "queue_backend": "in_process", "auto_start_queue_worker": False, "api_workers": 2})()):
            self.assertFalse(module._should_enable_reload())


if __name__ == "__main__":
    unittest.main()
