from app.infrastructure.learning.repository import LearningArchiveMongoRepository
from app.infrastructure.learning.schemas import ExternalKnowledgeSearchQuery


class SearchExternalKnowledgeUseCase:
    def __init__(self, repository: LearningArchiveMongoRepository) -> None:
        self.repository = repository

    async def execute(self, query: ExternalKnowledgeSearchQuery) -> list[dict]:
        return await self.repository.search_external_knowledge(
            query_text=query.query,
            source_name=query.source_name,
            language=query.language,
            framework=query.framework,
            vulnerability_category=query.vulnerability_category,
            weakness_id=query.weakness_id,
            tags=query.tags,
            limit=query.limit,
            offset=query.offset,
        )

