import asyncio
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.learning.benchmark import LearningBenchmarkService


class FakeLearningRepository:
    def __init__(self) -> None:
        self.runs: dict[str, dict] = {}
        self.suites: set[str] = set()
        self.cases: dict[str, dict] = {}
        self._counter = 0

    async def upsert_benchmark_suite(self, suite_name: str, *, metadata: dict | None = None) -> str:
        self.suites.add(suite_name)
        return f"suite_{suite_name}"

    async def upsert_benchmark_case(self, case: dict) -> str:
        case_id = str(case.get("case_id", f"case_{len(self.cases) + 1}"))
        self.cases[case_id] = case
        return case_id

    async def create_benchmark_run(self, *, suite_name: str, benchmark_type: str, metadata: dict | None = None) -> str:
        self._counter += 1
        run_id = f"run_{self._counter}"
        self.runs[run_id] = {"suite_name": suite_name, "status": "running", "metrics": {}}
        return run_id

    async def finalize_benchmark_run(self, run_id: str, *, status: str, metrics: dict, artifacts: dict | None = None) -> None:
        self.runs[run_id]["status"] = status
        self.runs[run_id]["metrics"] = metrics
        self.runs[run_id]["artifacts"] = artifacts or {}

    async def list_archive_items(self, *, statuses: list[str] | None = None, limit: int = 250) -> list[dict]:
        data = [
            {"record_type": "finding", "status": "validated", "severity": "high", "vulnerability_category": "sql", "body_chunk_count": 1},
            {"record_type": "finding", "status": "candidate", "severity": "medium", "vulnerability_category": "xss", "body_chunk_count": 1},
            {"record_type": "patch", "status": "verified_fixed", "payload": {"file_paths": ["a.py"]}},
            {"record_type": "patch", "status": "applied", "payload": {"file_paths": ["a.py", "b.py"]}},
            {"record_type": "verification", "status": "verified_partial"},
        ]
        if not statuses:
            return data[:limit]
        return [item for item in data if item["status"] in statuses][:limit]

    async def list_benchmark_cases(self, *, suite_name: str, limit: int = 500) -> list[dict]:
        return [case for case in self.cases.values() if case.get("suite_name") == suite_name][:limit]

    async def list_recent_ingestion_audits(self, *, limit: int = 200) -> list[dict]:
        return [
            {"status": "completed", "details": {"skipped_items": 1}},
            {"status": "completed", "details": {"skipped_items": 0}},
        ]

    async def count_normalization_failures(self, *, run_id: str | None = None) -> int:
        return 0


class LearningBenchmarkTests(unittest.TestCase):
    def test_runs_all_benchmark_suites(self):
        service = LearningBenchmarkService(FakeLearningRepository())
        summaries = asyncio.run(service.run_all())
        self.assertEqual(len(summaries), 4)
        self.assertTrue(all(item.run_id for item in summaries))

    def test_detection_suite_returns_metrics_contract(self):
        service = LearningBenchmarkService(FakeLearningRepository())
        summary = asyncio.run(service.run_suite("detection"))
        self.assertIn("detection_rate", summary.metrics)
        self.assertIn("false_positive_rate", summary.metrics)
        self.assertIn("evidence_presence_rate", summary.metrics)

    def test_benchmark_skeleton_seeds_detection_cases(self):
        repository = FakeLearningRepository()
        service = LearningBenchmarkService(repository)
        asyncio.run(service.ensure_benchmark_skeleton())
        self.assertGreaterEqual(len(repository.cases), 6)
        suites = {case.get("suite_name") for case in repository.cases.values()}
        self.assertIn("detection", suites)


if __name__ == "__main__":
    unittest.main()
