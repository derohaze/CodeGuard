import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.learning.benchmark_seed_data import build_default_detection_ground_truth_cases


class LearningBenchmarkSeedDataTests(unittest.TestCase):
    def test_default_detection_seed_cases_have_required_fields(self):
        cases = build_default_detection_ground_truth_cases()
        self.assertGreaterEqual(len(cases), 6)
        for case in cases:
            self.assertEqual(case["suite_name"], "detection")
            self.assertTrue(case["case_id"])
            self.assertTrue(case["content_fingerprint"])
            self.assertEqual(case["source_system"], "juliet_test_suite_seed")


if __name__ == "__main__":
    unittest.main()
