import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.ai.prompt_loader import ACTIVE_RUNTIME_PROMPTS, PROMPT_PACKS, PROMPTS_DIR, load_prompt_pack


class PromptLoaderTests(unittest.TestCase):
    def test_fix_prompt_pack_includes_shared_remediation_rules(self) -> None:
        prompt = load_prompt_pack("fix_prompt.md")

        self.assertIn("Shared remediation policy", prompt)
        self.assertIn("command injection", prompt.lower())
        self.assertIn("NoSQL injection", prompt)

    def test_path_reviewer_prompt_pack_includes_framework_focus(self) -> None:
        prompt = load_prompt_pack("path_reviewer.md")

        self.assertIn("Shared security scan rules", prompt)
        self.assertIn("GraphQL", prompt)
        self.assertIn("Java servlet", prompt)

    def test_repository_mapper_prompt_pack_includes_all_scan_modules(self) -> None:
        prompt = load_prompt_pack("repository_mapper.md")

        self.assertIn("Prompt module: framework_detector", prompt)
        self.assertIn("Prompt module: scope_planner", prompt)
        self.assertIn("Prompt module: graph_builder", prompt)
        self.assertIn("Prompt module: source_sink_locator", prompt)
        self.assertIn("Prompt module: risk_prioritizer", prompt)
        self.assertIn("Prompt module: segment_planner", prompt)

    def test_verdict_prompt_pack_includes_reporting_modules(self) -> None:
        prompt = load_prompt_pack("verdict_analyst.md")

        self.assertIn("Prompt module: score_analyst", prompt)
        self.assertIn("Prompt module: annotation_builder", prompt)
        self.assertIn("Prompt module: report_writer", prompt)

    def test_all_prompt_markdown_files_are_accounted_for_by_runtime_packs(self) -> None:
        prompt_files = {path.name for path in PROMPTS_DIR.glob("*.md")}
        referenced = set(ACTIVE_RUNTIME_PROMPTS)
        for parts in PROMPT_PACKS.values():
            referenced.update(parts)

        self.assertSetEqual(set(), prompt_files - referenced)


if __name__ == "__main__":
    unittest.main()
