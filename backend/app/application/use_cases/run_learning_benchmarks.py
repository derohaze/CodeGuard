from app.infrastructure.learning.benchmark import BENCHMARK_SUITES, BenchmarkRunSummary, LearningBenchmarkService


class RunLearningBenchmarksUseCase:
    def __init__(self, service: LearningBenchmarkService) -> None:
        self.service = service

    async def execute(self, suites: list[str] | None = None) -> list[BenchmarkRunSummary]:
        requested = [item.strip().lower() for item in (suites or []) if item.strip()]
        if not requested:
            return await self.service.run_all()
        invalid = [suite for suite in requested if suite not in BENCHMARK_SUITES]
        if invalid:
            raise ValueError(f"Unsupported benchmark suites: {', '.join(sorted(invalid))}")
        results: list[BenchmarkRunSummary] = []
        for suite in requested:
            results.append(await self.service.run_suite(suite))
        return results

