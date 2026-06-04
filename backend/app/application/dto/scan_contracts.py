from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StartScanRequest(BaseModel):
    source_path: str = Field(min_length=1)
    target_type: Literal["folder", "file"]
    preset: Literal["safe", "balanced", "aggressive"] = "balanced"
    scan_mode: Literal["fast", "deep"] = "deep"
    interactive: bool = True


class AttackSimulationResponse(BaseModel):
    input: str
    execution: str
    result: str


class FixSuggestionResponse(BaseModel):
    id: str
    label: str
    profile: str
    description: str


class AnnotationResponse(BaseModel):
    file: str
    lineStart: int
    lineEnd: int
    severity: Literal["critical", "high", "medium", "low"]
    tone: Literal["red", "yellow"]
    title: str
    confidence: int
    evidence: str
    pathHint: str


class FindingResponse(BaseModel):
    id: str
    severity: Literal["critical", "high", "medium", "low"]
    title: str
    file: str
    line: int
    line_end: int
    category: str
    confidence: int
    summary: str
    impact: str
    explanation: str
    evidence: str
    attack_simulation: AttackSimulationResponse
    audit_log: list[str]
    fix_suggestions: list[FixSuggestionResponse]
    remediation_status: Literal[
        "open",
        "patch_generated",
        "applied",
        "verified_fixed",
        "verified_partial",
        "validation_failed",
        "rejected",
        "rolled_back",
    ] = "open"
    approval_status: Literal["not_required", "pending", "approved", "rejected", "escalated"] = "not_required"
    approval_history: list[dict] = Field(default_factory=list)
    applied_strategy_id: str | None = None
    remediation_notes: list[str] = Field(default_factory=list)
    attempted_strategy_ids: list[str] = Field(default_factory=list)
    decision_summary: dict | None = None


class SeveritySummary(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class ScanJobResponse(BaseModel):
    id: str
    session_id: str
    type: Literal["scan"]
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    stage: str
    progress: int
    attempts: int
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AnalysisBriefResponse(BaseModel):
    score_explanation: str = ""
    potential_risks: list[str] = Field(default_factory=list)
    security_observations: list[str] = Field(default_factory=list)
    analysis_limitations: list[str] = Field(default_factory=list)
    attack_thinking: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class SessionSummaryResponse(BaseModel):
    id: str
    title: str
    repo: str
    time: str
    unread: bool
    status: Literal["queued", "scanning", "completed", "failed"]
    preview: str
    scan_mode: Literal["fast", "deep"]
    critical_count: int
    warning_count: int
    findings_count: int
    candidate_findings_count: int = 0
    progress: int
    phase_progress: int = 0
    progress_message: str
    current_phase: str
    elapsed_seconds: int
    progress_logs: list[str]
    progress_counters: dict | None = None
    runtime_metrics: dict | None = None
    scan_plan: dict | None = None
    repository_summary: str | None = None
    analysis_brief: AnalysisBriefResponse | None = None
    repository_inventory: dict | None = None
    framework_profile: dict | None = None
    repository_graph: dict | None = None
    graph_summary: dict | None = None
    security_registry: dict | None = None
    segmentation_summary: dict | None = None
    path_inventory: dict | None = None
    path_summary: dict | None = None
    review_queue_summary: dict | None = None
    annotations: list[AnnotationResponse] = Field(default_factory=list)
    annotation_summary: dict | None = None
    coverage_snapshot: dict | None = None
    coverage_summary: str | None = None
    coverage_percent: int
    reviewed_files_count: int
    eligible_files_count: int
    reviewed_blocks_count: int
    total_blocks_count: int
    reviewed_lines_count: int
    total_lines_count: int
    traced_paths_count: int
    total_paths_count: int
    skipped_files_count: int
    high_risk_files_count: int
    is_safe: bool
    security_score: int | None
    score_rationale: dict | None = None
    target_type: Literal["folder", "file"]
    source_path: str
    preset: Literal["safe", "balanced", "aggressive"]
    interactive: bool = True
    last_verification: dict | None = None
    latest_scan_job: ScanJobResponse | None = None
    workflow_summary: dict | None = None
    created_at: datetime
    updated_at: datetime


class ScanSessionDetailResponse(BaseModel):
    session: SessionSummaryResponse
    issues: SeveritySummary
    findings: list[FindingResponse]
    candidate_findings: list[FindingResponse] = Field(default_factory=list)
    verdict: Literal["safe", "issues_found"]
    completed_at: datetime | None = None
    error_message: str | None = None


class WorkflowRepoIntelligenceSummaryResponse(BaseModel):
    session_count: int
    hotspot_count: int
    critical_hotspots: int
    identity_zones: int
    exposure_zones: int
    data_zones: int
    coverage_zones: int
    top_hotspot_label: str
    top_repositories: dict[str, int] = Field(default_factory=dict)


class WorkflowTeamPostureSummaryResponse(BaseModel):
    session_count: int
    hotspot_count: int
    critical_hotspots: int
    control_drag: int
    risk_drag: int
    coverage_drag: int
    throughput_drag: int
    top_hotspot_label: str


class WorkflowServiceExposureSummaryResponse(BaseModel):
    session_count: int
    hotspot_count: int
    critical_hotspots: int
    boundary_drag: int
    network_drag: int
    path_drag: int
    entrypoint_drag: int
    top_hotspot_label: str
    top_services: dict[str, int] = Field(default_factory=dict)


class WorkflowRepoHotspotItemResponse(BaseModel):
    session_id: str
    repo: str
    hotspot_class: str
    priority: str
    label: str


class WorkflowRepoHotspotFeedResponse(BaseModel):
    items: list[WorkflowRepoHotspotItemResponse] = Field(default_factory=list)


class WorkflowTeamPostureItemResponse(BaseModel):
    session_id: str
    repo: str
    status: str
    hotspot_class: str
    priority: str
    finding_count: int
    coverage_percent: int


class WorkflowTeamPostureFeedResponse(BaseModel):
    items: list[WorkflowTeamPostureItemResponse] = Field(default_factory=list)


class WorkflowServiceExposureItemResponse(BaseModel):
    session_id: str
    repo: str
    hotspot_class: str
    priority: str
    label: str


class WorkflowServiceExposureFeedResponse(BaseModel):
    items: list[WorkflowServiceExposureItemResponse] = Field(default_factory=list)
