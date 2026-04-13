from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.dto.learning_contracts import (
    ArchiveSessionResponse,
    BenchmarkRunRequest,
    BenchmarkRunResponse,
    BenchmarkRunResult,
    ExternalKnowledgeIngestionRequest,
    ExternalKnowledgeIngestionResponse,
    ExternalKnowledgeItemResponse,
    ExternalKnowledgeSearchResponse,
    FeedbackEventRequest,
    FeedbackEventResponse,
)
from app.application.use_cases.archive_learning_session import ArchiveLearningSessionUseCase
from app.application.use_cases.ingest_external_knowledge import IngestExternalKnowledgeUseCase
from app.application.use_cases.record_feedback_event import RecordFeedbackEventUseCase
from app.application.use_cases.run_learning_benchmarks import RunLearningBenchmarksUseCase
from app.application.use_cases.search_external_knowledge import SearchExternalKnowledgeUseCase
from app.infrastructure.learning.schemas import ExternalKnowledgeSearchQuery, ExternalKnowledgeSourceSpec
from app.presentation.api.v1.routes.dependencies import (
    get_archive_learning_session_use_case,
    get_ingest_external_knowledge_use_case,
    get_record_feedback_event_use_case,
    get_run_learning_benchmarks_use_case,
    get_search_external_knowledge_use_case,
)


router = APIRouter()


@router.post("/learning/archive/sessions/{session_id}", response_model=ArchiveSessionResponse)
async def archive_session(
    session_id: str,
    use_case: ArchiveLearningSessionUseCase = Depends(get_archive_learning_session_use_case),
):
    summary = await use_case.execute(session_id)
    if summary.status == "failed" and summary.failures > 0 and summary.items_written == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found for archive.")
    return ArchiveSessionResponse(
        run_id=summary.run_id,
        session_id=summary.session_id,
        items_written=summary.items_written,
        items_skipped=summary.items_skipped,
        failures=summary.failures,
        status=summary.status,
    )


@router.post("/learning/external-ingestion", response_model=ExternalKnowledgeIngestionResponse)
async def ingest_external_knowledge(
    payload: ExternalKnowledgeIngestionRequest,
    use_case: IngestExternalKnowledgeUseCase = Depends(get_ingest_external_knowledge_use_case),
):
    if not payload.sources:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one external source is required.")
    sources = [ExternalKnowledgeSourceSpec.model_validate(item.model_dump()) for item in payload.sources]
    result = await use_case.execute(sources)
    return ExternalKnowledgeIngestionResponse(
        run_id=result.run_id,
        source_count=result.source_count,
        item_written=result.item_written,
        item_skipped=result.item_skipped,
        item_failed=result.item_failed,
        status=result.status,
    )


@router.get("/learning/knowledge/search", response_model=ExternalKnowledgeSearchResponse)
async def search_external_knowledge(
    query: str = "",
    source_name: str | None = None,
    language: str | None = None,
    framework: str | None = None,
    vulnerability_category: str | None = None,
    weakness_id: str | None = None,
    tags: str | None = Query(default=None, description="Comma separated tags."),
    limit: int = 20,
    offset: int = 0,
    use_case: SearchExternalKnowledgeUseCase = Depends(get_search_external_knowledge_use_case),
):
    request = ExternalKnowledgeSearchQuery(
        query=query,
        source_name=source_name,
        language=language,
        framework=framework,
        vulnerability_category=vulnerability_category,
        weakness_id=weakness_id,
        tags=[tag.strip() for tag in (tags or "").split(",") if tag.strip()],
        limit=limit,
        offset=offset,
    )
    records = await use_case.execute(request)
    return ExternalKnowledgeSearchResponse(
        items=[
            ExternalKnowledgeItemResponse(
                item_id=str(item.get("item_id") or item.get("_id")),
                source_name=str(item.get("source_name", "")),
                source_version=str(item.get("source_version", "")),
                item_type=item.get("item_type"),
                language=item.get("language"),
                framework=item.get("framework"),
                vulnerability_category=item.get("vulnerability_category"),
                weakness_id=item.get("weakness_id"),
                title=item.get("title"),
                summary=item.get("summary"),
                tags=item.get("tags", []),
                original_reference=item.get("original_reference"),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
            )
            for item in records
        ]
    )


@router.post("/learning/feedback", response_model=FeedbackEventResponse)
async def record_feedback_event(
    payload: FeedbackEventRequest,
    use_case: RecordFeedbackEventUseCase = Depends(get_record_feedback_event_use_case),
):
    event_id = await use_case.execute(
        session_id=payload.session_id,
        finding_id=payload.finding_id,
        patch_id=payload.patch_id,
        status=payload.status,
        actor_type=payload.actor_type,
        outcome=payload.outcome,
        notes=payload.notes,
        repository_fingerprint=payload.repository_fingerprint,
        language=payload.language,
        framework=payload.framework,
        vulnerability_category=payload.vulnerability_category,
    )
    return FeedbackEventResponse(event_id=event_id, status=payload.status)


@router.post("/learning/benchmarks/run", response_model=BenchmarkRunResponse)
async def run_learning_benchmarks(
    payload: BenchmarkRunRequest,
    use_case: RunLearningBenchmarksUseCase = Depends(get_run_learning_benchmarks_use_case),
):
    try:
        results = await use_case.execute(payload.suites)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BenchmarkRunResponse(
        results=[
            BenchmarkRunResult(
                run_id=item.run_id,
                suite_name=item.suite_name,
                status=item.status,
                metrics=item.metrics,
                artifacts=item.artifacts,
            )
            for item in results
        ]
    )

