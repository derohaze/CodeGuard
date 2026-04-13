from app.infrastructure.learning.benchmark import LearningBenchmarkService
from app.infrastructure.learning.repository import LearningArchiveMongoRepository


async def ensure_learning_bootstrap() -> None:
    repository = LearningArchiveMongoRepository()
    benchmark_service = LearningBenchmarkService(repository)
    await benchmark_service.ensure_benchmark_skeleton()

