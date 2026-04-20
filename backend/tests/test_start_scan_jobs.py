import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application.dto.scan_contracts import StartScanRequest
from app.application.use_cases.scan.start_scan import StartScanUseCase


class FakeSessionRepository:
    def __init__(self) -> None:
        self.created = None
        self.updated = []

    async def create(self, session):
        self.created = session
        return session

    async def update(self, session_id, updates):
        self.updated.append((session_id, updates))
        return self.created

    async def get_by_id(self, session_id: str):
        if self.created is not None and self.created.id == session_id:
            return self.created
        return None


class FakeJobRepository:
    def __init__(self) -> None:
        self.created = None
        self.updated = []

    async def create(self, job):
        self.created = job
        return job

    async def update(self, job_id, updates):
        self.updated.append((job_id, updates))
        return self.created

    async def get_by_id(self, job_id: str):
        if self.created is not None and self.created.id == job_id:
            return self.created
        return None

    async def list_active(self, limit: int = 200):
        return []

    async def count_active(self):
        return 0

    async def find_active_by_source(self, source_fingerprint):
        return None


class StartScanJobTests(unittest.TestCase):
    def test_start_scan_creates_session_and_queued_job_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")
            session_repo = FakeSessionRepository()
            job_repo = FakeJobRepository()
            use_case = StartScanUseCase(session_repo, job_repo)

            session, job = asyncio.run(
                use_case.execute(
                    StartScanRequest(
                        source_path=str(root),
                        target_type="folder",
                        preset="balanced",
                        scan_mode="deep",
                    )
                )
            )

        self.assertEqual(session.id, job.session_id)
        self.assertEqual(session.source_fingerprint, job.source_fingerprint)
        self.assertEqual(job.status, "queued")
        self.assertIsNotNone(session.latest_scan_job)
        self.assertEqual(session.latest_scan_job["id"], job.id)
        self.assertEqual(session.latest_scan_job["status"], "queued")
        self.assertEqual(job.queue_name, "aegix:queue:scan")


if __name__ == "__main__":
    unittest.main()
