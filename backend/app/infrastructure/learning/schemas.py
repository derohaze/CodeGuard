from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


LEARNING_SCHEMA_VERSION = "1.0.0"
BENCHMARK_SCHEMA_VERSION = "1.0.0"
CHUNK_POLICY_VERSION = "1.0.0"

StatusVocabulary = Literal[
    "suspected",
    "candidate",
    "validated",
    "rejected",
    "false_positive",
    "patch_generated",
    "patch_approved",
    "patch_rejected",
    "applied",
    "verified_fixed",
    "verified_partial",
    "validation_failed",
    "rolled_back",
]

RecordType = Literal[
    "finding",
    "patch",
    "verification",
    "approval",
    "feedback",
    "audit",
    "benchmark_case",
    "security_pattern",
    "framework_rule",
]


class NormalizedFindingRecord(BaseModel):
    schema_version: str = LEARNING_SCHEMA_VERSION
    record_type: Literal["finding"] = "finding"
    record_id: str
    source_system: str
    status: StatusVocabulary
    created_at: datetime
    updated_at: datetime
    language: str | None = None
    framework: str | None = None
    repository_fingerprint: str | None = None
    file_paths: list[str] = Field(default_factory=list)
    vulnerability_category: str | None = None
    severity: str | None = None
    confidence: int | None = None
    source_metadata: dict = Field(default_factory=dict)
    sink_metadata: dict = Field(default_factory=dict)
    sanitizer_metadata: dict = Field(default_factory=dict)
    path_metadata: dict = Field(default_factory=dict)
    evidence_metadata: dict = Field(default_factory=dict)
    remediation_metadata: dict = Field(default_factory=dict)
    human_outcome: dict = Field(default_factory=dict)
    verification_outcome: dict = Field(default_factory=dict)
    raw_reference: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    content_fingerprint: str


class NormalizedPatchRecord(BaseModel):
    schema_version: str = LEARNING_SCHEMA_VERSION
    record_type: Literal["patch"] = "patch"
    record_id: str
    source_system: str
    status: StatusVocabulary
    created_at: datetime
    updated_at: datetime
    language: str | None = None
    framework: str | None = None
    repository_fingerprint: str | None = None
    vulnerability_category: str | None = None
    severity: str | None = None
    confidence: int | None = None
    file_paths: list[str] = Field(default_factory=list)
    remediation_metadata: dict = Field(default_factory=dict)
    verification_outcome: dict = Field(default_factory=dict)
    human_outcome: dict = Field(default_factory=dict)
    raw_reference: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    content_fingerprint: str


class NormalizedBenchmarkCase(BaseModel):
    schema_version: str = BENCHMARK_SCHEMA_VERSION
    record_type: Literal["benchmark_case"] = "benchmark_case"
    case_id: str
    suite_name: str
    source_system: str
    vulnerability_category: str | None = None
    language: str | None = None
    framework: str | None = None
    severity: str | None = None
    expected_status: StatusVocabulary | None = None
    ground_truth_confidence: int = 100
    provenance: dict = Field(default_factory=dict)
    payload: dict = Field(default_factory=dict)
    content_fingerprint: str


class NormalizedSecurityPattern(BaseModel):
    schema_version: str = LEARNING_SCHEMA_VERSION
    record_type: Literal["security_pattern"] = "security_pattern"
    pattern_id: str
    source_name: str
    source_version: str | None = None
    item_type: str
    language: str | None = None
    framework: str | None = None
    vulnerability_category: str | None = None
    weakness_id: str | None = None
    title: str
    summary: str | None = None
    unsafe_pattern: str | None = None
    safe_pattern: str | None = None
    bad_example: str | None = None
    good_example: str | None = None
    remediation_notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    license_notes: str | None = None
    original_reference: str | None = None
    raw_reference: dict = Field(default_factory=dict)
    content_fingerprint: str


class NormalizedFrameworkRule(BaseModel):
    schema_version: str = LEARNING_SCHEMA_VERSION
    record_type: Literal["framework_rule"] = "framework_rule"
    rule_id: str
    source_name: str
    source_version: str | None = None
    language: str | None = None
    framework: str | None = None
    vulnerability_category: str | None = None
    weakness_id: str | None = None
    title: str
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    original_reference: str | None = None
    raw_reference: dict = Field(default_factory=dict)
    content_fingerprint: str


class NormalizedFeedbackEvent(BaseModel):
    schema_version: str = LEARNING_SCHEMA_VERSION
    record_type: Literal["feedback"] = "feedback"
    event_id: str
    source_system: str
    created_at: datetime
    status: StatusVocabulary
    session_id: str | None = None
    finding_id: str | None = None
    patch_id: str | None = None
    actor_type: str = "human_reviewer"
    outcome: str | None = None
    notes: str | None = None
    repository_fingerprint: str | None = None
    language: str | None = None
    framework: str | None = None
    vulnerability_category: str | None = None
    raw_reference: dict = Field(default_factory=dict)
    content_fingerprint: str


class ExternalKnowledgeSourceSpec(BaseModel):
    source_name: str
    source_version: str
    endpoint: str
    item_type: str
    language: str | None = None
    framework: str | None = None
    vulnerability_category: str | None = None
    weakness_id: str | None = None
    license_notes: str | None = None
    original_reference: str | None = None
    tags: list[str] = Field(default_factory=list)


class ExternalKnowledgeSearchQuery(BaseModel):
    query: str = ""
    source_name: str | None = None
    language: str | None = None
    framework: str | None = None
    vulnerability_category: str | None = None
    weakness_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    limit: int = 20
    offset: int = 0

