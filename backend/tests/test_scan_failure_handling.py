import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.exceptions import ExternalAIServiceError
from app.infrastructure.services.scan_execution_service import ScanExecutionService, create_initial_session


class FakeRepository:
    def __init__(self, session):
        self.session = session

    async def create(self, session):
        self.session = session
        return session

    async def update(self, session_id, updates):
        if self.session.id != session_id:
            return None
        for key, value in updates.items():
            if hasattr(self.session, key):
                setattr(self.session, key, value)
        return self.session

    async def get_by_id(self, session_id):
        return self.session if self.session.id == session_id else None

    async def list_recent(self, limit: int = 25):
        return [self.session][:limit]

    async def delete(self, session_id):
        return self.session.id == session_id

    async def delete_all(self):
        return 1


class FailingAIClient:
    async def map_repository(self, **kwargs):
        raise ExternalAIServiceError(
            "NVIDIA is temporarily unavailable. Retry the scan shortly.",
            provider="nvidia",
            retryable=False,
        )


class SummaryFailingAIClient:
    async def map_repository(self, **kwargs):
        return {
            "review_note": "",
            "repository_summary": "repo",
            "coverage_note": "",
            "trust_boundaries": [],
            "priority_paths": [],
        }

    async def review_paths(self, **kwargs):
        return {"review_note": "", "repository_summary": "", "findings": []}

    async def validate_findings(self, **kwargs):
        return {"review_note": "", "safe_summary": "", "findings": []}

    async def summarize_verdict(self, **kwargs):
        raise ExternalAIServiceError(
            "NVIDIA returned malformed output.",
            provider="nvidia",
            retryable=True,
            failure_kind="output_format",
        )

    async def explain_finding(self, **kwargs):
        return {}

    async def draft_fix_strategies(self, **kwargs):
        return {}

    async def validate_remediation(self, **kwargs):
        return {}


class ScanFailureHandlingTests(unittest.TestCase):
    def test_provider_failure_marks_session_failed_without_safe_score(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")
            session = create_initial_session(str(root), "folder", "balanced", "deep")
            repository = FakeRepository(session)
            service = ScanExecutionService(repository, FailingAIClient())

            asyncio.run(service.run(session.id))

            self.assertEqual(repository.session.status, "failed")
            self.assertIsNone(repository.session.security_score)
            self.assertEqual(repository.session.coverage_percent, 0)
            self.assertEqual(repository.session.findings, [])
            self.assertEqual(repository.session.candidate_findings, [])
            self.assertFalse(repository.session.is_safe)
            self.assertEqual(
                repository.session.error_message,
                "Khwarizm could not complete the scan because the configured AI runtime was temporarily unavailable. Retry shortly.",
            )
            self.assertEqual(repository.session.score_rationale["status"], "failed")

    def test_verdict_summary_failure_falls_back_to_deterministic_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")
            session = create_initial_session(str(root), "folder", "balanced", "deep")
            repository = FakeRepository(session)
            service = ScanExecutionService(repository, SummaryFailingAIClient())

            asyncio.run(service.run(session.id))

            self.assertEqual(repository.session.status, "completed")
            self.assertIsInstance(repository.session.repository_summary, str)
            self.assertTrue(repository.session.repository_summary)


if __name__ == "__main__":
    unittest.main()
