from pathlib import Path
import sys
import tempfile
import unittest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.services.segmentation_planning import build_scan_work_units


def _block(file_path: str, index: int, *, focus: str) -> dict:
    return {
        "block_id": f"{file_path}:{index}",
        "kind": "window",
        "start_line": index * 10 + 1,
        "end_line": index * 10 + 8,
        "focuses": [focus],
        "snippet": f"{index}: code",
    }


class SegmentationPlanningTests(unittest.TestCase):
    def test_fast_mode_prioritizes_high_signal_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            low = root / "low.py"
            high = root / "high.py"
            low.write_text("print('low')\n", encoding="utf-8")
            high.write_text("print('high')\n", encoding="utf-8")

            work_units = build_scan_work_units(
                scan_mode="fast",
                files=[low, high],
                source_root=root,
                repository_artifacts={
                    "hotspot_files": [
                        {"file": "low.py", "score": 1, "reasons": ["request entrypoint"], "imports": []},
                        {"file": "high.py", "score": 9, "reasons": ["subprocess"], "imports": []},
                    ]
                },
                repository_map={
                    "priority_paths": [],
                },
                file_segments=[
                    {"file": "low.py", "line_count": 40, "block_count": 1, "blocks": [_block("low.py", 1, focus="request flow")]},
                    {"file": "high.py", "line_count": 40, "block_count": 1, "blocks": [_block("high.py", 1, focus="command execution")]},
                ],
                target_type="folder",
                traced_paths={"paths": []},
            )

            self.assertGreaterEqual(len(work_units["review_items"]), 1)
            self.assertEqual(work_units["review_items"][0]["file"], "high.py")

    def test_fast_mode_applies_per_file_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sample = root / "api.py"
            sample.write_text("print('x')\n", encoding="utf-8")
            blocks = [_block("api.py", index, focus="command execution") for index in range(1, 7)]

            work_units = build_scan_work_units(
                scan_mode="fast",
                files=[sample],
                source_root=root,
                repository_artifacts={"hotspot_files": [{"file": "api.py", "score": 12, "reasons": ["subprocess"], "imports": []}]},
                repository_map={"priority_paths": []},
                file_segments=[{"file": "api.py", "line_count": 300, "block_count": len(blocks), "blocks": blocks}],
                target_type="folder",
                traced_paths={"paths": []},
            )

            self.assertLessEqual(len(work_units["review_items"]), 3)


if __name__ == "__main__":
    unittest.main()
