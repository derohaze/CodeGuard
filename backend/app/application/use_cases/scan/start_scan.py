from bson import ObjectId

from app.application.dto.scan_contracts import StartScanRequest
from app.core.config import get_settings
from app.core.exceptions import WorkflowConflictError
from app.domain.entities.scan_job import ScanJobEntity, build_scan_job_snapshot
from app.domain.entities.scan import ScanSessionEntity, utc_now
from app.domain.repositories.scan_job_repository import ScanJobRepository
from app.domain.repositories.scan_repository import ScanSessionRepository
from app.infrastructure.services.scan.scan_execution_service import create_initial_session
from app.infrastructure.services.scan.scan_lock_manager import ScanLockManager
from app.infrastructure.services.workflow.workflow_persistence import WorkflowPersistenceService


class StartScanUseCase:
    def __init__(
        self,
        repository: ScanSessionRepository,
        job_repository: ScanJobRepository,
        workflow_persistence: WorkflowPersistenceService | None = None,
        scan_lock_manager: ScanLockManager | None = None,
    ) -> None:
        self.repository = repository
        self.job_repository = job_repository
        self.workflow_persistence = workflow_persistence
        self.scan_lock_manager = scan_lock_manager

    async def execute(self, request: StartScanRequest) -> tuple[ScanSessionEntity, ScanJobEntity]:
        settings = get_settings()
        session = create_initial_session(
            source_path=request.source_path,
            target_type=request.target_type,
            preset=request.preset,
            scan_mode=request.scan_mode,
            interactive=request.interactive,
        )
        await self._reconcile_stale_active_jobs(limit=max(settings.global_concurrent_scans_limit * 4, 200))
        active_jobs = await self.job_repository.count_active()
        if active_jobs >= settings.global_concurrent_scans_limit:
            raise WorkflowConflictError("The scan queue is at capacity. Retry after current scans complete.")
        existing_job = await self.job_repository.find_active_by_source(session.source_fingerprint)
        if existing_job is not None:
            stale_cleared = await self._cancel_stale_job_if_recoverable(existing_job)
            if stale_cleared:
                existing_job = await self.job_repository.find_active_by_source(session.source_fingerprint)
        if existing_job is not None:
            raise WorkflowConflictError("A scan is already running for this source.")

        lock_lease = None
        if self.scan_lock_manager is not None:
            lock_lease = await self.scan_lock_manager.acquire_submission_locks(
                session_id=session.id,
                source_fingerprint=session.source_fingerprint,
            )
            if lock_lease is None:
                raise WorkflowConflictError("A scan is already queued or running for this source.")
        job = ScanJobEntity(
            id=str(ObjectId()),
            session_id=session.id,
            source_fingerprint=session.source_fingerprint,
            status="queued",
            stage="queued",
            progress=0,
            attempts=0,
            queue_name=settings.scan_queue_name,
            submission_key=f"{session.source_fingerprint}:{session.id}",
            lock_owner=lock_lease.owner if lock_lease is not None else None,
        )
        session.latest_scan_job = build_scan_job_snapshot(job)
        try:
            created_session = await self.repository.create(session)
            created_job = await self.job_repository.create(job)
            if self.workflow_persistence is not None:
                await self.workflow_persistence.record_audit(
                    session_id=created_session.id,
                    entity_type="scan_job",
                    entity_id=created_job.id,
                    action="scan.queued",
                    payload={
                        "repo": created_session.repo,
                        "target_type": created_session.target_type,
                        "scan_mode": created_session.scan_mode,
                        "source_fingerprint": created_session.source_fingerprint,
                        "queue_name": created_job.queue_name,
                    },
                )
            return created_session, created_job
        except Exception:
            if self.scan_lock_manager is not None:
                await self.scan_lock_manager.release_submission_locks(lock_lease)
            raise

    async def _reconcile_stale_active_jobs(self, *, limit: int) -> None:
        for active_job in await self.job_repository.list_active(limit=limit):
            await self._cancel_stale_job_if_recoverable(active_job)

    async def _cancel_stale_job_if_recoverable(self, job: ScanJobEntity) -> bool:
        stale_reason = await self._resolve_stale_reason(job)
        if stale_reason is None:
            return False
        await self._cancel_active_job(
            job,
            f"Recovered stale active scan job: {stale_reason}.",
        )
        return True

    async def _resolve_stale_reason(self, job: ScanJobEntity) -> str | None:
        session = await self.repository.get_by_id(job.session_id)
        if session is None:
            return "session record is missing"
        if session.status in {"completed", "failed"}:
            return f"session is already {session.status}"
        if self.scan_lock_manager is None:
            return None

        lease = await self.scan_lock_manager.build_lease_from_job(
            session_id=job.session_id,
            source_fingerprint=job.source_fingerprint,
            owner=job.lock_owner,
        )
        if lease is None:
            return "lock metadata is missing"
        if not await self.scan_lock_manager.has_submission_locks(lease):
            return "submission locks are missing or expired"
        return None

    async def _cancel_active_job(self, job: ScanJobEntity, reason: str) -> None:
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
                "error_message": reason,
                "finished_at": utc_now(),
            },
        )

    async def mark_dispatch_failed(self, session: ScanSessionEntity, job: ScanJobEntity, error_message: str) -> None:
        if self.scan_lock_manager is not None:
            await self.scan_lock_manager.release_submission_locks(
                await self.scan_lock_manager.build_lease_from_job(
                    session_id=job.session_id,
                    source_fingerprint=job.source_fingerprint,
                    owner=job.lock_owner,
                )
            )
        failed_snapshot = build_scan_job_snapshot(
            ScanJobEntity(
                id=job.id,
                session_id=job.session_id,
                source_fingerprint=job.source_fingerprint,
                status="failed",
                stage="dispatch_failed",
                progress=100,
                attempts=job.attempts,
                queue_name=job.queue_name,
                submission_key=job.submission_key,
                lock_owner=job.lock_owner,
                error_message=error_message,
                created_at=job.created_at,
                started_at=job.started_at,
            )
        )
        await self.job_repository.update(
            job.id,
            {
                "status": "failed",
                "stage": "dispatch_failed",
                "progress": 100,
                "error_message": error_message,
            },
        )
        await self.repository.update(
            session.id,
            {
                "status": "failed",
                "progress": 100,
                "phase_progress": 100,
                "progress_message": "Scan dispatch failed.",
                "current_phase": "Dispatch failed",
                "error_message": error_message,
                "latest_scan_job": failed_snapshot,
            },
        )
        if self.workflow_persistence is not None:
            await self.workflow_persistence.record_audit(
                session_id=session.id,
                entity_type="scan_job",
                entity_id=job.id,
                action="scan.dispatch_failed",
                payload={"error_message": error_message},
            )
