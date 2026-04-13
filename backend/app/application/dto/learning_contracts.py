from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ArchiveSessionResponse(BaseModel):
    run_id: str
    session_id: str
    items_written: int
    items_skipped: int
    failures: int
    status: str


class ExternalKnowledgeSourceRequest(BaseModel):
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


class ExternalKnowledgeIngestionRequest(BaseModel):
    sources: list[ExternalKnowledgeSourceRequest]


class ExternalKnowledgeIngestionResponse(BaseModel):
    run_id: str
    source_count: int
    item_written: int
    item_skipped: int
    item_failed: int
    status: str


class ExternalKnowledgeItemResponse(BaseModel):
    item_id: str
    source_name: str
    source_version: str
    item_type: str | None = None
    language: str | None = None
    framework: str | None = None
    vulnerability_category: str | None = None
    weakness_id: str | None = None
    title: str | None = None
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    original_reference: str | None = None
    created_at: datetime
    updated_at: datetime


class ExternalKnowledgeSearchResponse(BaseModel):
    items: list[ExternalKnowledgeItemResponse] = Field(default_factory=list)


class FeedbackEventRequest(BaseModel):
    session_id: str | None = None
    finding_id: str | None = None
    patch_id: str | None = None
    status: str
    actor_type: str = "human_reviewer"
    outcome: str | None = None
    notes: str | None = None
    repository_fingerprint: str | None = None
    language: str | None = None
    framework: str | None = None
    vulnerability_category: str | None = None


class FeedbackEventResponse(BaseModel):
    event_id: str
    status: str


class BenchmarkRunRequest(BaseModel):
    suites: list[str] = Field(default_factory=list)


class BenchmarkRunResult(BaseModel):
    run_id: str
    suite_name: str
    status: str
    metrics: dict
    artifacts: dict


class BenchmarkRunResponse(BaseModel):
    results: list[BenchmarkRunResult]

