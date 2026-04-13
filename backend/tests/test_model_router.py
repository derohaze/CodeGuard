import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.ai.orchestration.model_router import ModelRouter


class ModelRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = ModelRouter(
            small_model="openai/gpt-oss-20b",
            large_model="openai/gpt-oss-120b",
            overflow_model="openai/gpt-oss-120b-overflow",
        )

    def test_breadth_tasks_prefer_small_model(self):
        models = self.router.route_candidates("repository_map")
        self.assertEqual(models[0], "openai/gpt-oss-20b")
        self.assertIn("openai/gpt-oss-120b-overflow", models)

    def test_depth_tasks_prefer_large_model(self):
        models = self.router.route_candidates("finding_validate")
        self.assertEqual(models[0], "openai/gpt-oss-120b")
        self.assertIn("openai/gpt-oss-120b-overflow", models)


if __name__ == "__main__":
    unittest.main()
