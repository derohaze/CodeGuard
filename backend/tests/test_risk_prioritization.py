from pathlib import Path
import sys
import unittest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.services.risk_prioritization import prioritize_review_queue


class RiskPrioritizationTests(unittest.TestCase):
    def test_prioritizes_cross_file_command_paths_above_sanitized_paths(self) -> None:
        prioritized = prioritize_review_queue(
            work_items=[
                {"file": "safe.py", "signal_score": "9", "review_focus": "filesystem checks", "start_line": "10"},
                {"file": "danger.py", "signal_score": "7", "review_focus": "command execution", "start_line": "20"},
            ],
            path_units=[
                {
                    "sink": {"file": "safe.py", "line": 10, "kind": "filesystem_access"},
                    "path_type": "intra_file",
                    "has_sanitizer": True,
                    "confidence": 93,
                    "line_sequence": [8, 9, 10],
                },
                {
                    "sink": {"file": "danger.py", "line": 20, "kind": "command_execution"},
                    "path_type": "cross_file",
                    "has_sanitizer": False,
                    "confidence": 84,
                    "line_sequence": [3, 12, 20],
                },
            ],
            scan_mode="fast",
        )

        self.assertEqual(prioritized["review_items"][0]["file"], "danger.py")
        self.assertEqual(prioritized["path_units"][0]["sink"]["file"], "danger.py")
        self.assertGreaterEqual(prioritized["review_queue_summary"]["high_risk_path_units"], 1)


if __name__ == "__main__":
    unittest.main()
