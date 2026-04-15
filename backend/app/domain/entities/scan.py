from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


Severity = Literal["critical", "high", "medium", "low"]
SessionStatus = Literal["queued", "scanning", "completed", "failed"]
TargetType = Literal["folder", "file"]
ScanPreset = Literal["safe", "balanced", "aggressive"]
ScanMode = Literal["fast", "deep"]
RemediationStatus = Literal[
    "open",
    "patch_generated",
    "applied",
    "verified_fixed",
    "verified_partial",
    "validation_failed",
    "rejected",
    "rolled_back",
]
ApprovalStatus = Literal["not_required", "pending", "approved", "rejected", "escalated"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class FindingEntity:
    id: str
    severity: Severity
    title: str
    file: str
    line: int
    line_end: int
    category: str
    confidence: int
    summary: str
    impact: str
    attack_input: str
    attack_execution: str
    attack_result: str
    audit_log: list[str]
    explanation: str
    fix_suggestions: list[dict[str, str]]
    evidence: str
    remediation_status: RemediationStatus = "open"
    approval_status: ApprovalStatus = "not_required"
    approval_history: list[dict] = field(default_factory=list)
    applied_strategy_id: str | None = None
    remediation_notes: list[str] = field(default_factory=list)
    attempted_strategy_ids: list[str] = field(default_factory=list)
    decision_summary: dict | None = None


@dataclass(slots=True)
class ScanSessionEntity:
    id: str
    title: str
    repo: str
    source_path: str
    target_type: TargetType
    preset: ScanPreset
    scan_mode: ScanMode
    status: SessionStatus
    progress: int
    progress_message: str
    current_phase: str
    elapsed_seconds: int
    preview: str
    source_fingerprint: str | None = None
    progress_logs: list[str] = field(default_factory=list)
    phase_progress: int = 0
    progress_counters: dict | None = None
    runtime_metrics: dict | None = None
    scan_plan: dict | None = None
    repository_summary: str | None = None
    analysis_brief: dict | None = None
    repository_inventory: dict | None = None
    framework_profile: dict | None = None
    repository_graph: dict | None = None
    graph_summary: dict | None = None
    security_registry: dict | None = None
    segmentation_summary: dict | None = None
    path_inventory: dict | None = None
    path_summary: dict | None = None
    review_queue_summary: dict | None = None
    annotations: list[dict] = field(default_factory=list)
    annotation_summary: dict | None = None
    coverage_snapshot: dict | None = None
    coverage_summary: str | None = None
    coverage_percent: int = 0
    reviewed_files_count: int = 0
    eligible_files_count: int = 0
    reviewed_blocks_count: int = 0
    total_blocks_count: int = 0
    reviewed_lines_count: int = 0
    total_lines_count: int = 0
    traced_paths_count: int = 0
    total_paths_count: int = 0
    skipped_files_count: int = 0
    high_risk_files_count: int = 0
    is_safe: bool = False
    unread: bool = True
    security_score: int | None = None
    score_rationale: dict | None = None
    findings: list[FindingEntity] = field(default_factory=list)
    candidate_findings: list[FindingEntity] = field(default_factory=list)
    remediation_checkpoints: list[dict] = field(default_factory=list)
    last_verification: dict | None = None
    latest_scan_job: dict | None = None
    workflow_summary: dict | None = None
    workflow_events: list[dict] = field(default_factory=list)
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None
