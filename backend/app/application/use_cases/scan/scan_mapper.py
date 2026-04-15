from datetime import timezone

from app.application.dto.scan_contracts import (
    AnalysisBriefResponse,
    AttackSimulationResponse,
    FindingResponse,
    FixSuggestionResponse,
    ScanJobResponse,
    ScanSessionDetailResponse,
    SessionSummaryResponse,
    SeveritySummary,
)
from app.domain.entities.scan import FindingEntity, ScanSessionEntity
from app.infrastructure.services.remediation.decision_summary import build_finding_decision_summary
from app.infrastructure.services.workflow.workflow_summary import build_workflow_summary


def format_relative_time(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def map_finding(entity: FindingEntity) -> FindingResponse:
    return FindingResponse(
        id=entity.id,
        severity=entity.severity,
        title=entity.title,
        file=entity.file,
        line=entity.line,
        line_end=entity.line_end,
        category=entity.category,
        confidence=entity.confidence,
        summary=entity.summary,
        impact=entity.impact,
        explanation=entity.explanation,
        evidence=entity.evidence,
        attack_simulation=AttackSimulationResponse(
            input=entity.attack_input,
            execution=entity.attack_execution,
            result=entity.attack_result,
        ),
        audit_log=entity.audit_log,
        fix_suggestions=[FixSuggestionResponse(**item) for item in entity.fix_suggestions],
        remediation_status=entity.remediation_status,
        approval_status=entity.approval_status,
        approval_history=entity.approval_history,
        applied_strategy_id=entity.applied_strategy_id,
        remediation_notes=entity.remediation_notes,
        attempted_strategy_ids=entity.attempted_strategy_ids,
        decision_summary=entity.decision_summary or build_finding_decision_summary(entity),
    )


def count_severities(findings: list[FindingEntity]) -> SeveritySummary:
    summary = SeveritySummary()
    for finding in findings:
        current = getattr(summary, finding.severity)
        setattr(summary, finding.severity, current + 1)
    return summary


def map_session_summary(entity: ScanSessionEntity) -> SessionSummaryResponse:
    severity_counts = count_severities(entity.findings)
    return SessionSummaryResponse(
        id=entity.id,
        title=entity.title,
        repo=entity.repo,
        time=format_relative_time(entity.updated_at),
        unread=entity.unread,
        status=entity.status,
        preview=entity.preview,
        scan_mode=entity.scan_mode,
        critical_count=severity_counts.critical,
        warning_count=severity_counts.high + severity_counts.medium + severity_counts.low,
        findings_count=len(entity.findings),
        candidate_findings_count=len(entity.candidate_findings),
        progress=entity.progress,
        phase_progress=entity.phase_progress,
        progress_message=entity.progress_message,
        current_phase=entity.current_phase,
        elapsed_seconds=entity.elapsed_seconds,
        progress_logs=entity.progress_logs,
        progress_counters=entity.progress_counters,
        runtime_metrics=entity.runtime_metrics,
        scan_plan=entity.scan_plan,
        repository_summary=entity.repository_summary,
        analysis_brief=AnalysisBriefResponse(**entity.analysis_brief) if entity.analysis_brief else None,
        repository_inventory=entity.repository_inventory,
        framework_profile=entity.framework_profile,
        repository_graph=entity.repository_graph,
        graph_summary=entity.graph_summary,
        security_registry=entity.security_registry,
        segmentation_summary=entity.segmentation_summary,
        path_inventory=entity.path_inventory,
        path_summary=entity.path_summary,
        review_queue_summary=entity.review_queue_summary,
        annotations=entity.annotations,
        annotation_summary=entity.annotation_summary,
        coverage_snapshot=entity.coverage_snapshot,
        coverage_summary=entity.coverage_summary,
        coverage_percent=entity.coverage_percent,
        reviewed_files_count=entity.reviewed_files_count,
        eligible_files_count=entity.eligible_files_count,
        reviewed_blocks_count=entity.reviewed_blocks_count,
        total_blocks_count=entity.total_blocks_count,
        reviewed_lines_count=entity.reviewed_lines_count,
        total_lines_count=entity.total_lines_count,
        traced_paths_count=entity.traced_paths_count,
        total_paths_count=entity.total_paths_count,
        skipped_files_count=entity.skipped_files_count,
        high_risk_files_count=entity.high_risk_files_count,
        is_safe=entity.is_safe,
        security_score=entity.security_score,
        score_rationale=entity.score_rationale,
        target_type=entity.target_type,
        source_path=entity.source_path,
        preset=entity.preset,
        last_verification=entity.last_verification,
        latest_scan_job=ScanJobResponse(**entity.latest_scan_job) if entity.latest_scan_job else None,
        workflow_summary=entity.workflow_summary or build_workflow_summary(entity),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def map_session_detail(entity: ScanSessionEntity) -> ScanSessionDetailResponse:
    return ScanSessionDetailResponse(
        session=map_session_summary(entity),
        issues=count_severities(entity.findings),
        findings=[map_finding(item) for item in entity.findings],
        candidate_findings=[map_finding(item) for item in entity.candidate_findings],
        verdict="safe" if entity.is_safe else "issues_found",
        completed_at=entity.completed_at,
        error_message=entity.error_message,
    )
