from pathlib import Path
import sys
import tempfile
import time
import unittest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.services.scan_identity import (
    build_analysis_cache_key,
    build_repository_snapshot_fingerprint,
    build_source_fingerprint,
)


class ScanIdentityTests(unittest.TestCase):
    def test_repository_snapshot_fingerprint_changes_when_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sample = root / "app.py"
            sample.write_text("print('safe')\n", encoding="utf-8")
            first = build_repository_snapshot_fingerprint(root, [sample])

            # Ensure mtime changes on fast filesystems.
            time.sleep(0.01)
            sample.write_text("print('unsafe')\n", encoding="utf-8")
            second = build_repository_snapshot_fingerprint(root, [sample])

            self.assertNotEqual(first, second)

    def test_analysis_cache_key_changes_by_mode(self) -> None:
        source_fingerprint = build_source_fingerprint("/repo", "folder")
        snapshot = "abc123snapshot"

        deep_key = build_analysis_cache_key(
            source_fingerprint=source_fingerprint,
            snapshot_fingerprint=snapshot,
            scan_mode="deep",
            target_type="folder",
            preset="balanced",
        )
        fast_key = build_analysis_cache_key(
            source_fingerprint=source_fingerprint,
            snapshot_fingerprint=snapshot,
            scan_mode="fast",
            target_type="folder",
            preset="balanced",
        )

        self.assertNotEqual(deep_key, fast_key)


if __name__ == "__main__":
    unittest.main()
