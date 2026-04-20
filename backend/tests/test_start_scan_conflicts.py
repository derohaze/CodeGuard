import asyncio
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application.dto.scan_contracts import StartScanRequest
from app.application.use_cases.scan.start_scan import StartScanUseCase
from app.core.exceptions import WorkflowConflictError
from app.domain.entities.scan_job import ScanJobEntity


class FakeSessionRepository:
    def __init__(
        self,
        existing_session_ids: set[str] | None = None,
        sessions_by_id: dict[str, "_Session"] | None = None,
    ):
        self.existing_session_ids = existing_session_ids or set()
        self.sessions_by_id = sessions_by_id or {}

    async def create(self, session):
        return session

    async def update(self, session_id, updates):
        return None

    async def get_by_id(self, session_id: str):
        if session_id in self.sessions_by_id:
            return self.sessions_by_id[session_id]
        if session_id in self.existing_session_ids:
            return _Session(id=session_id, status="queued")
        return None


class FakeJobRepository:
    def __init__(self, *, active_count=0, active_job=None, active_jobs: list[ScanJobEntity] | None = None):
        self.active_count = active_count
        self.active_job = active_job
        self.active_jobs = list(active_jobs or [])
        self.updated: list[tuple[str, dict]] = []
        self.created = None

    async def create(self, job):
        self.created = job
        return job

    async def update(self, job_id, updates):
        self.updated.append((job_id, updates))
        for active_job in self.active_jobs:
            if active_job.id != job_id:
                continue
            for key, value in updates.items():
                setattr(active_job, key, value)
        return None

    async def get_by_id(self, job_id: str):
        if self.created is not None and self.created.id == job_id:
            return self.created
        for active_job in self.active_jobs:
            if active_job.id == job_id:
                return active_job
        return None

    async def list_active(self, limit: int = 200):
        active = [job for job in self.active_jobs if job.status in {"queued", "running"}]
        return active[:limit]

    async def count_active(self):
        if self.active_jobs:
            return sum(1 for job in self.active_jobs if job.status in {"queued", "running"})
        return self.active_count

    async def find_active_by_source(self, source_fingerprint):
        for active_job in reversed(self.active_jobs):
            if active_job.status in {"queued", "running"} and active_job.source_fingerprint == source_fingerprint:
                return active_job
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
            active_job = ScanJobEntity(
                id="job-1",
                session_id="session-1",
                source_fingerprint="fp-1",
                status="queued",
                stage="queued",
                lock_owner="lock-1",
            )
            use_case = StartScanUseCase(
                FakeSessionRepository(existing_session_ids={"session-1"}),
                FakeJobRepository(active_job=active_job),
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

    def test_clears_orphaned_active_job_before_starting_new_scan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")
            request = StartScanRequest(
                source_path=str(root),
                target_type="folder",
                preset="balanced",
                scan_mode="deep",
            )
            orphan_job = ScanJobEntity(
                id="job-orphan",
                session_id="session-missing",
                source_fingerprint="missing-fp",
                status="queued",
                stage="queued",
                lock_owner="lock-orphan",
            )

            class _LockManager:
                def __init__(self) -> None:
                    self.released = 0

                async def acquire_submission_locks(self, *, session_id: str, source_fingerprint: str):
                    @dataclass(slots=True)
                    class _Lease:
                        session_id: str
                        source_fingerprint: str
                        owner: str

                    return _Lease(session_id=session_id, source_fingerprint=source_fingerprint, owner="new-lock")

                async def build_lease_from_job(self, *, session_id: str, source_fingerprint: str | None, owner: str | None):
                    @dataclass(slots=True)
                    class _Lease:
                        session_id: str
                        source_fingerprint: str
                        owner: str

                    if not source_fingerprint or not owner:
                        return None
                    return _Lease(session_id=session_id, source_fingerprint=source_fingerprint, owner=owner)

                async def release_submission_locks(self, lease):
                    if lease is not None:
                        self.released += 1

            job_repo = FakeJobRepository(active_jobs=[orphan_job])
            lock_manager = _LockManager()
            use_case = StartScanUseCase(
                FakeSessionRepository(existing_session_ids=set()),
                job_repo,
                scan_lock_manager=lock_manager,
            )

            session, job = asyncio.run(use_case.execute(request))

            self.assertEqual(session.id, job.session_id)
            self.assertEqual(job.status, "queued")
            self.assertTrue(any(update[0] == "job-orphan" and update[1].get("status") == "cancelled" for update in job_repo.updated))
            self.assertEqual(lock_manager.released, 1)

    def test_clears_terminal_session_jobs_before_capacity_check(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")
            stale_job = ScanJobEntity(
                id="job-stale",
                session_id="session-complete",
                source_fingerprint="stale-fp",
                status="queued",
                stage="queued",
                lock_owner="stale-lock",
            )
            use_case = StartScanUseCase(
                FakeSessionRepository(
                    sessions_by_id={"session-complete": _Session(id="session-complete", status="completed")},
                ),
                FakeJobRepository(active_jobs=[stale_job]),
            )

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
            self.assertEqual(job.status, "queued")
            self.assertTrue(any(update[0] == "job-stale" and update[1].get("status") == "cancelled" for update in use_case.job_repository.updated))

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


@dataclass(slots=True)
class _Session:
    id: str
    status: str


if __name__ == "__main__":
    unittest.main()
