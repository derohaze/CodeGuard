import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.infrastructure.services.scan.penetration_sandbox import prepare_penetration_sandbox


class PenetrationSandboxTests(unittest.TestCase):
    def tearDown(self) -> None:
        for key in (
            "ARTIFACTS_DIR",
            "PENETRATION_SANDBOX_ENABLED",
            "PENETRATION_SANDBOX_MAX_FILES",
            "PENETRATION_SANDBOX_MAX_TOTAL_MB",
        ):
            os.environ.pop(key, None)
        get_settings.cache_clear()

    def test_prepare_penetration_sandbox_copies_only_selected_finding_files(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as artifacts_dir:
            repo_root = Path(repo_dir)
            (repo_root / "app").mkdir(parents=True, exist_ok=True)
            (repo_root / "app" / "api.py").write_text("print('api')\n", encoding="utf-8")
            (repo_root / "app" / "worker.py").write_text("print('worker')\n", encoding="utf-8")

            os.environ["ARTIFACTS_DIR"] = artifacts_dir
            os.environ["PENETRATION_SANDBOX_ENABLED"] = "true"
            os.environ["PENETRATION_SANDBOX_MAX_FILES"] = "10"
            os.environ["PENETRATION_SANDBOX_MAX_TOTAL_MB"] = "10"
            get_settings.cache_clear()

            sandbox = prepare_penetration_sandbox(
                session_id="scan-123",
                source_path=repo_root,
                source_root=repo_root,
                target_type="folder",
                findings=[{"file": "app/api.py"}, {"file": "app/api.py"}],
            )

            self.assertTrue(sandbox["enabled"])
            self.assertEqual(sandbox["mode"], "isolated_copy")
            self.assertEqual(sandbox["copied_files"], 1)
            workspace_root = Path(sandbox["workspace_root"])
            self.assertTrue((workspace_root / "app" / "api.py").exists())
            self.assertFalse((workspace_root / "app" / "worker.py").exists())

            manifest = json.loads(Path(sandbox["manifest_path"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["copied_files_count"], 1)
            self.assertEqual(manifest["copied_files"], ["app/api.py"])

    def test_prepare_penetration_sandbox_rejects_path_traversal_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as artifacts_dir:
            repo_root = Path(repo_dir)
            (repo_root / "safe.py").write_text("print('safe')\n", encoding="utf-8")

            os.environ["ARTIFACTS_DIR"] = artifacts_dir
            os.environ["PENETRATION_SANDBOX_ENABLED"] = "true"
            get_settings.cache_clear()

            sandbox = prepare_penetration_sandbox(
                session_id="scan-traversal",
                source_path=repo_root,
                source_root=repo_root,
                target_type="folder",
                findings=[{"file": "../outside.py"}, {"file": "safe.py"}],
            )

            manifest = json.loads(Path(sandbox["manifest_path"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["copied_files"], ["safe.py"])
            self.assertNotIn("../outside.py", manifest["copied_files"])

    def test_prepare_penetration_sandbox_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir)
            (repo_root / "main.py").write_text("print('x')\n", encoding="utf-8")

            os.environ["PENETRATION_SANDBOX_ENABLED"] = "false"
            get_settings.cache_clear()

            sandbox = prepare_penetration_sandbox(
                session_id="disabled",
                source_path=repo_root,
                source_root=repo_root,
                target_type="folder",
                findings=[{"file": "main.py"}],
            )

            self.assertFalse(sandbox["enabled"])
            self.assertEqual(sandbox["mode"], "disabled")


if __name__ == "__main__":
    unittest.main()
