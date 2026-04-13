import asyncio
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.entities.scan import FindingEntity, ScanSessionEntity
from app.domain.entities.scan_job import ScanJobEntity
from app.infrastructure.learning.archive import SecurityLearningArchiveService


class AsyncCursor:
    def __init__(self, items):
        self.items = items

    def sort(self, *args, **kwargs):
        return self

    def __aiter__(self):
        self._iter = iter(self.items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class FakeCollection:
    def __init__(self, items):
        self.items = items

    def find(self, *args, **kwargs):
        return AsyncCursor(self.items)


class FakeSessionRepository:
    def __init__(self, session):
        self.session = session

    async def get_by_id(self, session_id: str):
        return self.session if session_id == self.session.id else None


class FakeJobRepository:
    def __init__(self, jobs):
        self.jobs = jobs

    async def list_by_session(self, session_id: str, limit: int = 100):
        return [job for job in self.jobs if job.session_id == session_id]


class FakeLearningRepository:
    def __init__(self):
        self.items = []
        self.feedback = []
        self.failures = []
        self.finalized = None

    async def create_archive_run(self, *, trigger: str, source_system: str, metadata: dict | None = None):
        return "run-1"

    async def upsert_learning_archive_item(self, *, run_id: str, item: dict, large_body: str | None = None, body_type: str = "prose"):
        self.items.append(item)
        return f"item-{len(self.items)}", True

    async def record_feedback_event(self, event: dict):
        self.feedback.append(event)
        return f"evt-{len(self.feedback)}"

    async def record_normalization_failure(self, *, run_id: str, source_name: str, item_ref: str, error_message: str, payload_excerpt: str | None):
        self.failures.append(item_ref)
        return "failure-1"

    async def finalize_archive_run(self, run_id: str, *, status: str, metrics: dict):
        self.finalized = (run_id, status, metrics)


class LearningArchiveTests(unittest.TestCase):
    def test_archive_session_writes_normalized_items(self):
        finding = FindingEntity(
            id="f-1",
            severity="high",
            title="SQLi",
            file="api/users.py",
            line=11,
            line_end=11,
            category="sql_injection",
            confidence=90,
            summary="summary",
            impact="impact",
            attack_input="input",
            attack_execution="path",
            attack_result="result",
            audit_log=["a"],
            explanation="e",
            fix_suggestions=[],
            evidence="evidence",
            remediation_status="patch_generated",
            approval_status="approved",
            approval_history=[{"status": "approved", "note": "ok", "timestamp": datetime.now(timezone.utc)}],
        )
        session = ScanSessionEntity(
            id="session-1",
            title="scan",
            repo="repo",
            source_path="D:/repo",
            target_type="folder",
            preset="balanced",
            scan_mode="deep",
            status="completed",
            progress=100,
            progress_message="done",
            current_phase="done",
            elapsed_seconds=1,
            preview="preview",
            source_fingerprint="abc",
            findings=[finding],
        )
        jobs = [
            ScanJobEntity(
                id="job-1",
                session_id="session-1",
                source_fingerprint="abc",
                status="completed",
                stage="done",
                progress=100,
            )
        ]
        learning_repo = FakeLearningRepository()
        fake_db = {"audit_events": FakeCollection([]), "verification_runs": FakeCollection([])}
        with patch("app.infrastructure.learning.archive.get_database", return_value=fake_db):
            service = SecurityLearningArchiveService(
                session_repository=FakeSessionRepository(session),
                scan_job_repository=FakeJobRepository(jobs),
                learning_repository=learning_repo,
            )
            summary = asyncio.run(service.archive_session("session-1"))

        self.assertEqual(summary.status, "completed")
        self.assertGreaterEqual(summary.items_written, 2)
        self.assertEqual(learning_repo.failures, [])
        self.assertEqual(len(learning_repo.feedback), 1)


if __name__ == "__main__":
    unittest.main()

