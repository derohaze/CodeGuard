from app.infrastructure.learning.archive import ArchiveSummary, SecurityLearningArchiveService


class ArchiveLearningSessionUseCase:
    def __init__(self, service: SecurityLearningArchiveService) -> None:
        self.service = service

    async def execute(self, session_id: str) -> ArchiveSummary:
        return await self.service.archive_session(session_id)

