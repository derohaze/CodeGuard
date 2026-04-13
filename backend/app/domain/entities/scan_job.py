from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.domain.entities.scan import utc_now


ScanJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
ScanJobType = Literal["scan"]


@dataclass(slots=True)
class ScanJobEntity:
    id: str
    session_id: str
    source_fingerprint: str
    status: ScanJobStatus
    stage: str
    progress: int = 0
    job_type: ScanJobType = "scan"
    attempts: int = 0
    queue_name: str | None = None
    submission_key: str | None = None
    lock_owner: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None


def build_scan_job_snapshot(job: ScanJobEntity) -> dict:
    return {
        "id": job.id,
        "session_id": job.session_id,
        "source_fingerprint": job.source_fingerprint,
        "type": job.job_type,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "attempts": job.attempts,
        "queue_name": job.queue_name,
        "submission_key": job.submission_key,
        "lock_owner": job.lock_owner,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }
