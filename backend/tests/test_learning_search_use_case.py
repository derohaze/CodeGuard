import asyncio
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application.use_cases.search_external_knowledge import SearchExternalKnowledgeUseCase
from app.infrastructure.learning.schemas import ExternalKnowledgeSearchQuery


class FakeLearningRepository:
    async def search_external_knowledge(
        self,
        *,
        query_text: str,
        source_name: str | None,
        language: str | None,
        framework: str | None,
        vulnerability_category: str | None,
        weakness_id: str | None,
        tags: list[str] | None,
        limit: int,
        offset: int,
    ) -> list[dict]:
        if query_text == "sql":
            return [{"item_id": "item-1", "title": "SQL Injection"}]
        return []


class LearningSearchUseCaseTests(unittest.TestCase):
    def test_search_uses_keyword_and_returns_items(self):
        use_case = SearchExternalKnowledgeUseCase(FakeLearningRepository())
        response = asyncio.run(
            use_case.execute(
                ExternalKnowledgeSearchQuery(
                    query="sql",
                    language="python",
                    framework="fastapi",
                    limit=10,
                    offset=0,
                )
            )
        )
        self.assertEqual(len(response), 1)
        self.assertEqual(response[0]["item_id"], "item-1")


if __name__ == "__main__":
    unittest.main()

