from app.domain.entities.scan import utc_now
from app.domain.repositories.scan_job_repository import ScanJobRepository
from app.domain.repositories.scan_repository import ScanSessionRepository
from app.infrastructure.services.scan.scan_lock_manager import ScanLockManager
from app.infrastructure.services.workflow.workflow_persistence import WorkflowPersistenceService


class DeleteSessionUseCase:
    def __init__(
        self,
        repository: ScanSessionRepository,
        workflow_persistence: WorkflowPersistenceService | None = None,
        job_repository: ScanJobRepository | None = None,
        scan_lock_manager: ScanLockManager | None = None,
    ) -> None:
        self.repository = repository
        self.workflow_persistence = workflow_persistence
        self.job_repository = job_repository
        self.scan_lock_manager = scan_lock_manager

    async def execute(self, session_id: str) -> bool:
        await self._cancel_active_jobs(session_id)
        deleted = await self.repository.delete(session_id)
        if deleted and self.workflow_persistence is not None:
            await self.workflow_persistence.cleanup_session(session_id)
        return deleted

    async def _cancel_active_jobs(self, session_id: str) -> None:
        if self.job_repository is None:
            return
        jobs = await self.job_repository.list_by_session(session_id, limit=200)
        for job in jobs:
            if job.status not in {"queued", "running"}:
                continue
            if self.scan_lock_manager is not None:
                lease = await self.scan_lock_manager.build_lease_from_job(
                    session_id=job.session_id,
                    source_fingerprint=job.source_fingerprint,
                    owner=job.lock_owner,
                )
                await self.scan_lock_manager.release_submission_locks(lease)
            await self.job_repository.update(
                job.id,
                {
                    "status": "cancelled",
                    "stage": "cancelled",
                    "progress": 100,
                    "error_message": "Scan session deleted by user.",
                    "finished_at": utc_now(),
                },
            )
