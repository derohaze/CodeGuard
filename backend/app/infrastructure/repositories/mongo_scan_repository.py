from datetime import timezone

from bson import ObjectId

from app.domain.entities.scan import FindingEntity, ScanSessionEntity
from app.domain.repositories.scan_repository import ScanSessionRepository
from app.infrastructure.database.collections import FINDINGS_COLLECTION, SCAN_SESSIONS_COLLECTION
from app.infrastructure.database.mongo import get_database


class MongoScanSessionRepository(ScanSessionRepository):
    def __init__(self) -> None:
        database = get_database()
        self.collection = database[SCAN_SESSIONS_COLLECTION]
        self.findings_collection = database[FINDINGS_COLLECTION]

    async def list_recent_light(self, limit: int = 25) -> list[ScanSessionEntity]:
        cursor = (
            self.collection.find(
                {},
                {
                    "workflow_events": 0,
                    "remediation_checkpoints.original_content": 0,
                },
            )
            .sort("updated_at", -1)
            .limit(limit)
        )
        return [_document_to_entity(document) async for document in cursor]

    async def create(self, session: ScanSessionEntity) -> ScanSessionEntity:
        payload = _entity_to_document(session)
        payload["_id"] = ObjectId(session.id)
        await self.collection.insert_one(payload)
        await self._sync_findings(session)
        return session

    async def update(self, session_id: str, updates: dict) -> ScanSessionEntity | None:
        normalized = dict(updates)
        if "findings" in normalized:
            normalized["findings"] = [_finding_to_document(item) for item in normalized["findings"]]
        if "candidate_findings" in normalized:
            normalized["candidate_findings"] = [_finding_to_document(item) for item in normalized["candidate_findings"]]
        await self.collection.update_one({"_id": ObjectId(session_id)}, {"$set": normalized})
        updated = await self.get_by_id(session_id)
        if updated is not None and ("findings" in normalized or "candidate_findings" in normalized):
            await self._sync_findings(updated)
        return updated

    async def get_by_id(self, session_id: str) -> ScanSessionEntity | None:
        document = await self.collection.find_one({"_id": ObjectId(session_id)})
        if document is None:
            return None
        return _document_to_entity(document)

    async def list_recent(self, limit: int = 25) -> list[ScanSessionEntity]:
        cursor = self.collection.find().sort("updated_at", -1).limit(limit)
        return [_document_to_entity(document) async for document in cursor]

    async def delete(self, session_id: str) -> bool:
        result = await self.collection.delete_one({"_id": ObjectId(session_id)})
        await self.findings_collection.delete_many({"session_id": session_id})
        return result.deleted_count > 0

    async def delete_all(self) -> int:
        result = await self.collection.delete_many({})
        await self.findings_collection.delete_many({})
        return int(result.deleted_count)

    async def _sync_findings(self, session: ScanSessionEntity) -> None:
        documents = [
            _finding_record_to_document(
                session_id=session.id,
                scan_job_id=(session.latest_scan_job or {}).get("id"),
                finding=item,
                finding_kind="validated",
                repo=session.repo,
            )
            for item in session.findings
        ]
        documents.extend(
            _finding_record_to_document(
                session_id=session.id,
                scan_job_id=(session.latest_scan_job or {}).get("id"),
                finding=item,
                finding_kind="candidate",
                repo=session.repo,
            )
            for item in session.candidate_findings
        )
        await self.findings_collection.delete_many({"session_id": session.id})
        if documents:
            await self.findings_collection.insert_many(documents, ordered=False)


def _finding_to_document(finding: FindingEntity) -> dict:
    if isinstance(finding, dict):
        return dict(finding)
    return {
        "id": finding.id,
        "severity": finding.severity,
        "title": finding.title,
        "file": finding.file,
        "line": finding.line,
        "line_end": finding.line_end,
        "category": finding.category,
        "confidence": finding.confidence,
        "summary": finding.summary,
        "impact": finding.impact,
        "attack_input": finding.attack_input,
        "attack_execution": finding.attack_execution,
        "attack_result": finding.attack_result,
        "audit_log": finding.audit_log,
        "explanation": finding.explanation,
        "fix_suggestions": finding.fix_suggestions,
        "evidence": finding.evidence,
        "remediation_status": finding.remediation_status,
        "approval_status": finding.approval_status,
        "approval_history": finding.approval_history,
        "applied_strategy_id": finding.applied_strategy_id,
        "remediation_notes": finding.remediation_notes,
        "attempted_strategy_ids": finding.attempted_strategy_ids,
        "decision_summary": finding.decision_summary,
    }


def _finding_record_to_document(*, session_id: str, scan_job_id: str | None, finding: FindingEntity, finding_kind: str, repo: str) -> dict:
    return {
        "session_id": session_id,
        "scan_job_id": scan_job_id,
        "finding_id": finding.id,
        "finding_kind": finding_kind,
        "severity": finding.severity,
        "file_path": finding.file,
        "line_start": finding.line,
        "line_end": finding.line_end,
        "title": finding.title,
        "description": finding.summary,
        "status": finding.remediation_status,
        "fingerprint": finding.id,
        "category": finding.category,
        "confidence": finding.confidence,
        "repo": repo,
        "payload": _finding_to_document(finding),
    }


def _entity_to_document(session: ScanSessionEntity) -> dict:
    return {
        "session_id": session.id,
        "title": session.title,
        "repo": session.repo,
        "source_path": session.source_path,
        "source_fingerprint": session.source_fingerprint,
        "target_type": session.target_type,
        "preset": session.preset,
        "scan_mode": session.scan_mode,
        "status": session.status,
        "progress": session.progress,
        "phase_progress": session.phase_progress,
        "progress_message": session.progress_message,
        "current_phase": session.current_phase,
        "elapsed_seconds": session.elapsed_seconds,
        "preview": session.preview,
        "progress_logs": session.progress_logs,
        "progress_counters": session.progress_counters,
        "runtime_metrics": session.runtime_metrics,
        "scan_plan": session.scan_plan,
        "repository_summary": session.repository_summary,
        "analysis_brief": session.analysis_brief,
        "repository_inventory": session.repository_inventory,
        "framework_profile": session.framework_profile,
        "repository_graph": session.repository_graph,
        "graph_summary": session.graph_summary,
        "security_registry": session.security_registry,
        "segmentation_summary": session.segmentation_summary,
        "path_inventory": session.path_inventory,
        "path_summary": session.path_summary,
        "review_queue_summary": session.review_queue_summary,
        "annotations": session.annotations,
        "annotation_summary": session.annotation_summary,
        "coverage_snapshot": session.coverage_snapshot,
        "coverage_summary": session.coverage_summary,
        "coverage_percent": session.coverage_percent,
        "reviewed_files_count": session.reviewed_files_count,
        "eligible_files_count": session.eligible_files_count,
        "reviewed_blocks_count": session.reviewed_blocks_count,
        "total_blocks_count": session.total_blocks_count,
        "reviewed_lines_count": session.reviewed_lines_count,
        "total_lines_count": session.total_lines_count,
        "traced_paths_count": session.traced_paths_count,
        "total_paths_count": session.total_paths_count,
        "skipped_files_count": session.skipped_files_count,
        "high_risk_files_count": session.high_risk_files_count,
        "is_safe": session.is_safe,
        "unread": session.unread,
        "security_score": session.security_score,
        "score_rationale": session.score_rationale,
        "findings": [_finding_to_document(item) for item in session.findings],
        "candidate_findings": [_finding_to_document(item) for item in session.candidate_findings],
        "remediation_checkpoints": session.remediation_checkpoints,
        "last_verification": session.last_verification,
        "latest_scan_job": session.latest_scan_job,
        "workflow_summary": session.workflow_summary,
        "workflow_events": session.workflow_events,
        "error_message": session.error_message,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "completed_at": session.completed_at,
    }


def _document_to_entity(document: dict) -> ScanSessionEntity:
    findings = [
        FindingEntity(
            id=item["id"],
            severity=item["severity"],
            title=item["title"],
            file=item["file"],
            line=item["line"],
            line_end=item.get("line_end", item["line"]),
            category=item["category"],
            confidence=item["confidence"],
            summary=item["summary"],
            impact=item["impact"],
            attack_input=item["attack_input"],
            attack_execution=item["attack_execution"],
            attack_result=item["attack_result"],
            audit_log=item["audit_log"],
            explanation=item["explanation"],
            fix_suggestions=item["fix_suggestions"],
            evidence=item.get("evidence", ""),
            remediation_status=item.get("remediation_status", "open"),
            approval_status=item.get("approval_status", "not_required"),
            approval_history=item.get("approval_history", []),
            applied_strategy_id=item.get("applied_strategy_id"),
            remediation_notes=item.get("remediation_notes", []),
            attempted_strategy_ids=item.get("attempted_strategy_ids", []),
            decision_summary=item.get("decision_summary"),
        )
        for item in document.get("findings", [])
    ]
    candidate_findings = [
        FindingEntity(
            id=item["id"],
            severity=item["severity"],
            title=item["title"],
            file=item["file"],
            line=item["line"],
            line_end=item.get("line_end", item["line"]),
            category=item["category"],
            confidence=item["confidence"],
            summary=item["summary"],
            impact=item["impact"],
            attack_input=item["attack_input"],
            attack_execution=item["attack_execution"],
            attack_result=item["attack_result"],
            audit_log=item["audit_log"],
            explanation=item["explanation"],
            fix_suggestions=item["fix_suggestions"],
            evidence=item.get("evidence", ""),
            remediation_status=item.get("remediation_status", "open"),
            approval_status=item.get("approval_status", "not_required"),
            approval_history=item.get("approval_history", []),
            applied_strategy_id=item.get("applied_strategy_id"),
            remediation_notes=item.get("remediation_notes", []),
            attempted_strategy_ids=item.get("attempted_strategy_ids", []),
            decision_summary=item.get("decision_summary"),
        )
        for item in document.get("candidate_findings", [])
    ]
    created_at = document["created_at"]
    updated_at = document["updated_at"]
    completed_at = document.get("completed_at")
    return ScanSessionEntity(
        id=str(document["_id"]),
        title=document["title"],
        repo=document["repo"],
        source_path=document["source_path"],
        source_fingerprint=document.get("source_fingerprint"),
        target_type=document["target_type"],
        preset=document["preset"],
        scan_mode=document.get("scan_mode", "deep"),
        status=document["status"],
        progress=document["progress"],
        phase_progress=document.get("phase_progress", 0),
        progress_message=document["progress_message"],
        current_phase=document.get("current_phase", document.get("progress_message", "Queued")),
        elapsed_seconds=document.get("elapsed_seconds", 0),
        preview=document["preview"],
        progress_logs=document.get("progress_logs", []),
        progress_counters=document.get("progress_counters"),
        runtime_metrics=document.get("runtime_metrics"),
        scan_plan=document.get("scan_plan"),
        repository_summary=document.get("repository_summary"),
        analysis_brief=document.get("analysis_brief"),
        repository_inventory=document.get("repository_inventory"),
        framework_profile=document.get("framework_profile"),
        repository_graph=document.get("repository_graph"),
        graph_summary=document.get("graph_summary"),
        security_registry=document.get("security_registry"),
        segmentation_summary=document.get("segmentation_summary"),
        path_inventory=document.get("path_inventory"),
        path_summary=document.get("path_summary"),
        review_queue_summary=document.get("review_queue_summary"),
        annotations=document.get("annotations", []),
        annotation_summary=document.get("annotation_summary"),
        coverage_snapshot=document.get("coverage_snapshot"),
        coverage_summary=document.get("coverage_summary"),
        coverage_percent=document.get("coverage_percent", 0),
        reviewed_files_count=document.get("reviewed_files_count", 0),
        eligible_files_count=document.get("eligible_files_count", 0),
        reviewed_blocks_count=document.get("reviewed_blocks_count", 0),
        total_blocks_count=document.get("total_blocks_count", 0),
        reviewed_lines_count=document.get("reviewed_lines_count", 0),
        total_lines_count=document.get("total_lines_count", 0),
        traced_paths_count=document.get("traced_paths_count", 0),
        total_paths_count=document.get("total_paths_count", 0),
        skipped_files_count=document.get("skipped_files_count", 0),
        high_risk_files_count=document.get("high_risk_files_count", 0),
        is_safe=document.get("is_safe", False),
        unread=document.get("unread", True),
        security_score=document.get("security_score"),
        score_rationale=document.get("score_rationale"),
        findings=findings,
        candidate_findings=candidate_findings,
        remediation_checkpoints=document.get("remediation_checkpoints", []),
        last_verification=document.get("last_verification"),
        latest_scan_job=document.get("latest_scan_job"),
        workflow_summary=document.get("workflow_summary"),
        workflow_events=document.get("workflow_events", []),
        error_message=document.get("error_message"),
        created_at=created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo is None else created_at,
        updated_at=updated_at.replace(tzinfo=timezone.utc) if updated_at.tzinfo is None else updated_at,
        completed_at=completed_at.replace(tzinfo=timezone.utc) if completed_at and completed_at.tzinfo is None else completed_at,
    )
