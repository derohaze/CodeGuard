from app.infrastructure.learning.ingestion import ExternalKnowledgeIngestionService, IngestionSummary
from app.infrastructure.learning.schemas import ExternalKnowledgeSourceSpec


class IngestExternalKnowledgeUseCase:
    def __init__(self, service: ExternalKnowledgeIngestionService) -> None:
        self.service = service

    async def execute(self, sources: list[ExternalKnowledgeSourceSpec]) -> IngestionSummary:
        return await self.service.ingest(sources)

