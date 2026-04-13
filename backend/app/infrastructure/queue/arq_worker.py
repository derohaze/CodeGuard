from arq.connections import RedisSettings
from arq.worker import func

from app.core.config import get_settings
from app.infrastructure.ai.provider_factory import build_ai_client
from app.infrastructure.database.mongo import close_mongo, initialize_mongo
from app.infrastructure.repositories.mongo_scan_job_repository import MongoScanJobRepository
from app.infrastructure.repositories.mongo_scan_repository import MongoScanSessionRepository
from app.infrastructure.services.scan_lock_manager import ScanLockManager
from app.infrastructure.services.scan_execution_service import ScanExecutionService
from app.infrastructure.services.workflow_persistence import WorkflowPersistenceService
from app.infrastructure.repositories.mongo_audit_event_repository import MongoAuditEventRepository
from app.infrastructure.repositories.mongo_verification_run_repository import MongoVerificationRunRepository


async def run_scan_job(_ctx: dict, session_id: str, job_id: str) -> None:
    service = ScanExecutionService(
        MongoScanSessionRepository(),
        build_ai_client(),
        MongoScanJobRepository(),
        WorkflowPersistenceService(
            audit_events=MongoAuditEventRepository(),
            verification_runs=MongoVerificationRunRepository(),
        ),
        ScanLockManager(),
    )
    await service.run(session_id, job_id=job_id)


async def startup(_ctx: dict) -> None:
    await initialize_mongo()


async def shutdown(_ctx: dict) -> None:
    await close_mongo()


settings = get_settings()


class WorkerSettings:
    functions = [func(run_scan_job, name="run_scan_job")]
    queue_name = settings.scan_queue_name
    redis_settings = RedisSettings.from_dsn(settings.redis_url) if settings.redis_url else None
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = settings.worker_max_jobs
    job_timeout = settings.scan_job_timeout_seconds
