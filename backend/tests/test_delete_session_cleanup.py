import asyncio
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application.use_cases.session.delete_all_sessions import DeleteAllSessionsUseCase
from app.application.use_cases.session.delete_session import DeleteSessionUseCase
from app.domain.entities.scan_job import ScanJobEntity


@dataclass(slots=True)
class _Session:
    id: str


class _FakeSessionRepository:
    def __init__(self, sessions: list[_Session]) -> None:
        self.sessions = sessions
        self.deleted_session_ids: list[str] = []
        self.deleted_all = False

    async def delete(self, session_id: str) -> bool:
        self.deleted_session_ids.append(session_id)
        return any(item.id == session_id for item in self.sessions)

    async def delete_all(self) -> int:
        self.deleted_all = True
        return len(self.sessions)

    async def list_recent(self, limit: int = 25) -> list[_Session]:
        return self.sessions[:limit]


class _FakeJobRepository:
    def __init__(self, jobs_by_session: dict[str, list[ScanJobEntity]]) -> None:
        self.jobs_by_session = jobs_by_session
        self.updated: list[tuple[str, dict]] = []

    async def list_by_session(self, session_id: str, limit: int = 25) -> list[ScanJobEntity]:
        return self.jobs_by_session.get(session_id, [])[:limit]

    async def update(self, job_id: str, updates: dict):
        self.updated.append((job_id, updates))
        return None


class _FakeLockManager:
    def __init__(self) -> None:
        self.released: list[tuple[str, str, str]] = []

    async def build_lease_from_job(self, *, session_id: str, source_fingerprint: str | None, owner: str | None):
        if not source_fingerprint or not owner:
            return None
        return _FakeLease(session_id=session_id, source_fingerprint=source_fingerprint, owner=owner)

    async def release_submission_locks(self, lease):
        if lease is None:
            return
        self.released.append((lease.session_id, lease.source_fingerprint, lease.owner))


@dataclass(slots=True)
class _FakeLease:
    session_id: str
    source_fingerprint: str
    owner: str


class _FakeWorkflowPersistence:
    def __init__(self) -> None:
        self.cleaned_sessions: list[str] = []
        self.cleaned_all = False

    async def cleanup_session(self, session_id: str) -> None:
        self.cleaned_sessions.append(session_id)

    async def cleanup_all(self) -> None:
        self.cleaned_all = True


class DeleteSessionCleanupTests(unittest.TestCase):
    def test_delete_session_cancels_active_jobs_and_releases_locks(self) -> None:
        sessions = [_Session(id="session-1")]
        active_job = ScanJobEntity(
            id="job-1",
            session_id="session-1",
            source_fingerprint="fp-1",
            status="queued",
            stage="queued",
            lock_owner="lock-1",
        )
        finished_job = ScanJobEntity(
            id="job-2",
            session_id="session-1",
            source_fingerprint="fp-1",
            status="completed",
            stage="completed",
            lock_owner="lock-2",
        )
        repo = _FakeSessionRepository(sessions)
        jobs = _FakeJobRepository({"session-1": [active_job, finished_job]})
        locks = _FakeLockManager()
        workflow = _FakeWorkflowPersistence()
        use_case = DeleteSessionUseCase(repo, workflow, jobs, locks)

        deleted = asyncio.run(use_case.execute("session-1"))

        self.assertTrue(deleted)
        self.assertEqual(repo.deleted_session_ids, ["session-1"])
        self.assertEqual(workflow.cleaned_sessions, ["session-1"])
        self.assertEqual(len(jobs.updated), 1)
        self.assertEqual(jobs.updated[0][0], "job-1")
        self.assertEqual(jobs.updated[0][1]["status"], "cancelled")
        self.assertEqual(jobs.updated[0][1]["stage"], "cancelled")
        self.assertEqual(len(locks.released), 1)
        self.assertEqual(locks.released[0], ("session-1", "fp-1", "lock-1"))

    def test_delete_all_sessions_cancels_active_jobs_across_sessions(self) -> None:
        sessions = [_Session(id="session-a"), _Session(id="session-b")]
        job_a = ScanJobEntity(
            id="job-a",
            session_id="session-a",
            source_fingerprint="fp-a",
            status="running",
            stage="reviewing",
            lock_owner="owner-a",
        )
        job_b = ScanJobEntity(
            id="job-b",
            session_id="session-b",
            source_fingerprint="fp-b",
            status="queued",
            stage="queued",
            lock_owner="owner-b",
        )
        repo = _FakeSessionRepository(sessions)
        jobs = _FakeJobRepository({"session-a": [job_a], "session-b": [job_b]})
        locks = _FakeLockManager()
        workflow = _FakeWorkflowPersistence()
        use_case = DeleteAllSessionsUseCase(repo, workflow, jobs, locks)

        deleted_count = asyncio.run(use_case.execute())

        self.assertEqual(deleted_count, 2)
        self.assertTrue(repo.deleted_all)
        self.assertTrue(workflow.cleaned_all)
        self.assertEqual({job_id for job_id, _ in jobs.updated}, {"job-a", "job-b"})
        self.assertEqual(len(locks.released), 2)


if __name__ == "__main__":
    unittest.main()
