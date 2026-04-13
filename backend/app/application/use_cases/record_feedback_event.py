from datetime import datetime, timezone

from app.infrastructure.learning.normalization import normalize_feedback_event
from app.infrastructure.learning.repository import LearningArchiveMongoRepository


class RecordFeedbackEventUseCase:
    def __init__(self, repository: LearningArchiveMongoRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        *,
        session_id: str | None,
        finding_id: str | None,
        patch_id: str | None,
        status: str,
        actor_type: str,
        outcome: str | None,
        notes: str | None,
        repository_fingerprint: str | None,
        language: str | None,
        framework: str | None,
        vulnerability_category: str | None,
    ) -> str:
        normalized = normalize_feedback_event(
            {
                "session_id": session_id,
                "finding_id": finding_id,
                "patch_id": patch_id,
                "status": status,
                "actor_type": actor_type,
                "outcome": outcome,
                "notes": notes,
                "repository_fingerprint": repository_fingerprint,
                "language": language,
                "framework": framework,
                "vulnerability_category": vulnerability_category,
                "created_at": datetime.now(timezone.utc),
                "source_system": "manual_feedback",
            }
        )
        return await self.repository.record_feedback_event(normalized.model_dump())

