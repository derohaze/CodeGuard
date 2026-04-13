from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.entities.scan import FindingEntity
from app.domain.repositories.scan_job_repository import ScanJobRepository
from app.domain.repositories.scan_repository import ScanSessionRepository
from app.infrastructure.database.collections import AUDIT_EVENTS_COLLECTION, VERIFICATION_RUNS_COLLECTION
from app.infrastructure.database.mongo import get_database
from app.infrastructure.learning.normalization import (
    normalize_feedback_event,
    normalize_internal_finding,
    normalize_patch_record,
    normalize_status,
)
from app.infrastructure.learning.repository import LearningArchiveMongoRepository
from app.infrastructure.learning.schemas import NormalizedFindingRecord


@dataclass(slots=True)
class ArchiveSummary:
    run_id: str
    session_id: str
    items_written: int
    items_skipped: int
    failures: int
    status: str


class SecurityLearningArchiveService:
    def __init__(
        self,
        session_repository: ScanSessionRepository,
        scan_job_repository: ScanJobRepository,
        learning_repository: LearningArchiveMongoRepository,
    ) -> None:
        self.session_repository = session_repository
        self.scan_job_repository = scan_job_repository
        self.learning_repository = learning_repository
        database = get_database()
        self.audit_events = database[AUDIT_EVENTS_COLLECTION]
        self.verification_runs = database[VERIFICATION_RUNS_COLLECTION]

    async def archive_session(self, session_id: str) -> ArchiveSummary:
        run_id = await self.learning_repository.create_archive_run(
            trigger="session_archive",
            source_system="internal_scans",
            metadata={"session_id": session_id},
        )
        written = 0
        skipped = 0
        failures = 0
        session = await self.session_repository.get_by_id(session_id)
        if session is None:
            await self.learning_repository.finalize_archive_run(
                run_id,
                status="failed",
                metrics={"items_written": 0, "items_skipped": 0, "failures": 1, "reason": "session_not_found"},
            )
            return ArchiveSummary(run_id=run_id, session_id=session_id, items_written=0, items_skipped=0, failures=1, status="failed")

        now = datetime.now(timezone.utc)
        records: list[dict] = []
        for finding in session.findings:
            records.append(
                normalize_internal_finding(
                    session=session,
                    finding=finding,
                    source_system="internal_scans",
                    now=now,
                ).model_dump()
            )
            patch = normalize_patch_record(session=session, finding=finding, source_system="internal_scans", now=now)
            if patch is not None:
                records.append(patch.model_dump())

        for finding in session.candidate_findings:
            candidate_record = normalize_internal_finding(
                session=session,
                finding=finding,
                source_system="internal_scans",
                now=now,
            )
            candidate_dict = candidate_record.model_dump()
            candidate_dict["status"] = "candidate"
            records.append(candidate_dict)

        jobs = await self.scan_job_repository.list_by_session(session.id, limit=100)
        for job in jobs:
            status = normalize_status(job.status, default="candidate")
            record_payload = {
                "schema_version": "1.0.0",
                "record_type": "audit",
                "record_id": f"scan_job_{job.id}",
                "source_system": "scan_jobs",
                "status": status,
                "created_at": job.created_at,
                "updated_at": job.finished_at or job.started_at or job.created_at,
                "language": None,
                "framework": None,
                "repository_fingerprint": job.source_fingerprint,
                "file_paths": [],
                "vulnerability_category": None,
                "severity": None,
                "confidence": None,
                "source_metadata": {},
                "sink_metadata": {},
                "sanitizer_metadata": {},
                "path_metadata": {"stage": job.stage, "progress": job.progress},
                "evidence_metadata": {"attempts": job.attempts},
                "remediation_metadata": {"queue_name": job.queue_name, "submission_key": job.submission_key},
                "human_outcome": {},
                "verification_outcome": {},
                "raw_reference": {"job_id": job.id, "session_id": job.session_id},
                "tags": ["scan_job", status],
                "content_fingerprint": f"job_{job.id}_{status}",
            }
            records.append(record_payload)

        async for audit in self.audit_events.find({"$or": [{"session_id": session_id}, {"entity_id": session_id}]}).sort("created_at", -1):
            record_payload = {
                "schema_version": "1.0.0",
                "record_type": "audit",
                "record_id": f"audit_{audit.get('_id')}",
                "source_system": "audit_events",
                "status": normalize_status(audit.get("action"), default="candidate"),
                "created_at": audit.get("created_at") or now,
                "updated_at": audit.get("created_at") or now,
                "language": None,
                "framework": None,
                "repository_fingerprint": session.source_fingerprint,
                "file_paths": [],
                "vulnerability_category": None,
                "severity": None,
                "confidence": None,
                "source_metadata": {},
                "sink_metadata": {},
                "sanitizer_metadata": {},
                "path_metadata": {},
                "evidence_metadata": {},
                "remediation_metadata": {"payload": audit.get("payload", {})},
                "human_outcome": {},
                "verification_outcome": {},
                "raw_reference": {"audit_id": str(audit.get("_id"))},
                "tags": ["audit_event", str(audit.get("action", ""))],
                "content_fingerprint": f"audit_{audit.get('_id')}",
            }
            records.append(record_payload)

        async for verification in self.verification_runs.find({"session_id": session_id}).sort("created_at", -1):
            record_payload = {
                "schema_version": "1.0.0",
                "record_type": "verification",
                "record_id": f"verification_{verification.get('verification_id')}",
                "source_system": "verification_runs",
                "status": normalize_status(verification.get("status"), default="candidate"),
                "created_at": verification.get("created_at") or now,
                "updated_at": verification.get("updated_at") or verification.get("created_at") or now,
                "language": None,
                "framework": None,
                "repository_fingerprint": session.source_fingerprint,
                "file_paths": [],
                "vulnerability_category": verification.get("vulnerability_category"),
                "severity": verification.get("severity"),
                "confidence": verification.get("confidence"),
                "source_metadata": {},
                "sink_metadata": {},
                "sanitizer_metadata": {},
                "path_metadata": {},
                "evidence_metadata": {"checks": verification.get("checks", [])},
                "remediation_metadata": {"fix_id": verification.get("fix_id")},
                "human_outcome": {},
                "verification_outcome": verification,
                "raw_reference": {"verification_id": verification.get("verification_id")},
                "tags": ["verification_run"],
                "content_fingerprint": f"verification_{verification.get('verification_id')}",
            }
            records.append(record_payload)

        for finding in session.findings:
            for approval_event in finding.approval_history:
                feedback = normalize_feedback_event(
                    {
                        "session_id": session.id,
                        "finding_id": finding.id,
                        "status": approval_event.get("status", finding.approval_status),
                        "notes": approval_event.get("note"),
                        "outcome": approval_event.get("status"),
                        "source": approval_event,
                        "repository_fingerprint": session.source_fingerprint,
                        "language": _extract_language_hint(finding),
                        "framework": _extract_framework_hint(session.framework_profile),
                        "vulnerability_category": finding.category,
                        "created_at": approval_event.get("timestamp") or now,
                    }
                )
                await self.learning_repository.record_feedback_event(feedback.model_dump())

        for record in records:
            try:
                finding_record = NormalizedFindingRecord.model_validate(record) if record["record_type"] == "finding" else None
                large_body = None
                if finding_record is not None:
                    large_body = "\n".join(
                        line
                        for line in [
                            finding_record.evidence_metadata.get("evidence"),
                            finding_record.path_metadata.get("attack_execution"),
                        ]
                        if line
                    )
                _, inserted = await self.learning_repository.upsert_learning_archive_item(
                    run_id=run_id,
                    item=record,
                    large_body=large_body,
                    body_type="code",
                )
                if inserted:
                    written += 1
                else:
                    skipped += 1
            except Exception as exc:
                failures += 1
                await self.learning_repository.record_normalization_failure(
                    run_id=run_id,
                    source_name="internal_scans",
                    item_ref=str(record.get("record_id")),
                    error_message=str(exc),
                    payload_excerpt=str(record)[:1024],
                )

        status = "completed" if failures == 0 else "completed_with_failures"
        await self.learning_repository.finalize_archive_run(
            run_id,
            status=status,
            metrics={"items_written": written, "items_skipped": skipped, "failures": failures},
        )
        return ArchiveSummary(
            run_id=run_id,
            session_id=session_id,
            items_written=written,
            items_skipped=skipped,
            failures=failures,
            status=status,
        )


def _extract_framework_hint(framework_profile: dict | None) -> str | None:
    if not framework_profile:
        return None
    frameworks = framework_profile.get("frameworks")
    if isinstance(frameworks, list):
        for item in frameworks:
            if isinstance(item, str) and item and item != "unknown":
                return item.lower()
    return None


def _extract_language_hint(finding: FindingEntity) -> str | None:
    path = finding.file.lower()
    if path.endswith(".py"):
        return "python"
    if path.endswith(".ts") or path.endswith(".tsx"):
        return "typescript"
    if path.endswith(".js") or path.endswith(".jsx"):
        return "javascript"
    return None
