import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.ai.agents.detection_agent import DetectionAgent


class DetectionAgentTests(unittest.TestCase):
    def test_map_repository_delegates_to_ai_client(self) -> None:
        client = _FakeAIClient()
        agent = DetectionAgent(client)

        payload = asyncio.run(
            agent.map_repository(
                project_name="repo",
                source_path="D:/repo",
                repository_profile={"file_count": 1},
                repository_artifacts={"coverage": {}},
                preset="balanced",
            )
        )

        self.assertEqual(payload["review_note"], "mapped")
        client.map_repository.assert_awaited_once()

    def test_review_paths_delegates_to_ai_client(self) -> None:
        client = _FakeAIClient()
        agent = DetectionAgent(client)

        payload = asyncio.run(
            agent.review_paths(
                project_name="repo",
                source_path="D:/repo",
                repository_profile={},
                repository_map={},
                work_items=[{"file": "main.py", "snippet": "print('x')"}],
                batch_index=1,
                total_batches=1,
                preset="balanced",
            )
        )

        self.assertEqual(payload["review_note"], "reviewed")
        client.review_paths.assert_awaited_once()

    def test_validate_findings_delegates_to_ai_client(self) -> None:
        client = _FakeAIClient()
        agent = DetectionAgent(client)

        payload = asyncio.run(
            agent.validate_findings(
                project_name="repo",
                source_path="D:/repo",
                repository_profile={},
                repository_map={},
                findings=[{"file": "main.py", "line": 1, "title": "x"}],
                preset="balanced",
            )
        )

        self.assertEqual(payload["safe_summary"], "validated")
        client.validate_findings.assert_awaited_once()


class _FakeAIClient:
    def __init__(self) -> None:
        self.map_repository = AsyncMock(return_value={"review_note": "mapped"})
        self.review_paths = AsyncMock(return_value={"review_note": "reviewed", "findings": []})
        self.validate_findings = AsyncMock(return_value={"review_note": "", "safe_summary": "validated", "findings": []})


if __name__ == "__main__":
    unittest.main()
