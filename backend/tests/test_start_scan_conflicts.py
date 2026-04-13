import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application.dto.scan_contracts import StartScanRequest
from app.application.use_cases.start_scan import StartScanUseCase
from app.core.exceptions import WorkflowConflictError


class FakeSessionRepository:
    async def create(self, session):
        return session

    async def update(self, session_id, updates):
        return None


class FakeJobRepository:
    def __init__(self, *, active_count=0, active_job=None):
        self.active_count = active_count
        self.active_job = active_job

    async def create(self, job):
        return job

    async def update(self, job_id, updates):
        return None

    async def count_active(self):
        return self.active_count

    async def find_active_by_source(self, source_fingerprint):
        return self.active_job


class RejectingLockManager:
    async def acquire_submission_locks(self, *, session_id: str, source_fingerprint: str):
        return None


class StartScanConflictTests(unittest.TestCase):
    def test_rejects_when_global_limit_is_reached(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")
            use_case = StartScanUseCase(FakeSessionRepository(), FakeJobRepository(active_count=4))
            with self.assertRaises(WorkflowConflictError):
                asyncio.run(
                    use_case.execute(
                        StartScanRequest(
                            source_path=str(root),
                            target_type="folder",
                            preset="balanced",
                            scan_mode="deep",
                        )
                    )
                )

    def test_rejects_when_source_already_has_active_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")
            use_case = StartScanUseCase(
                FakeSessionRepository(),
                FakeJobRepository(active_job=object()),
            )
            with self.assertRaises(WorkflowConflictError):
                asyncio.run(
                    use_case.execute(
                        StartScanRequest(
                            source_path=str(root),
                            target_type="folder",
                            preset="balanced",
                            scan_mode="deep",
                        )
                    )
                )

    def test_rejects_when_lock_manager_cannot_acquire_submission_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")
            use_case = StartScanUseCase(
                FakeSessionRepository(),
                FakeJobRepository(),
                scan_lock_manager=RejectingLockManager(),
            )
            with self.assertRaises(WorkflowConflictError):
                asyncio.run(
                    use_case.execute(
                        StartScanRequest(
                            source_path=str(root),
                            target_type="folder",
                            preset="balanced",
                            scan_mode="deep",
                        )
                    )
                )


if __name__ == "__main__":
    unittest.main()
