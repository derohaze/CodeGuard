from __future__ import annotations

import json
import logging
from typing import Any

from app.infrastructure.ai.prompt_builder import build_penetration_system_prompt
from app.infrastructure.ai.tools.agent_loop import InteractiveAgentLoop, MaxStepsError
from app.infrastructure.ai.tools.registry import ToolRegistry
from app.infrastructure.ai.tools.shell_tool import ShellTool
from app.infrastructure.ai.tools.http_tool import HTTPTool
from app.infrastructure.ai.tools.file_tools import FileReadTool, FileWriteTool, FileEditTool
from app.infrastructure.ai.tools.web_tools import WebFetchTool, WebSearchTool
from app.infrastructure.ai.tools.search_tools import GlobTool, GrepTool
from app.infrastructure.ai.tools.coverage_tool import CoverageTool
from app.infrastructure.ai.tools.ask_user_tool import AskUserTool
from app.infrastructure.ai.tools.finding_tool import ConfirmFindingTool
from app.infrastructure.ai.tools.load_skill_tool import LoadSkillTool as ToolsLoadSkillTool
from app.infrastructure.ai.agents.penetration_tester.contracts import PenetrationReport
from app.infrastructure.coverage.store import CoverageStore
from app.infrastructure.skills.loader import LoadSkillTool as CoreLoadSkillTool
from app.infrastructure.skills.registry import SkillRegistry
from app.infrastructure.intelligence.continuous.store import IntelligenceStore
from app.infrastructure.redact import redact_text

logger = logging.getLogger(__name__)


class PenetrationTestAgent:
    def __init__(
        self,
        ai_client,
        skill_registry: SkillRegistry | None = None,
        coverage_store: CoverageStore | None = None,
        intelligence_store: IntelligenceStore | None = None,
    ):
        self.ai_client = ai_client
        self.skill_registry = skill_registry
        self.coverage_store = coverage_store
        self.intelligence_store = intelligence_store

    def _build_registry(self) -> ToolRegistry:
        reg = ToolRegistry()
        reg.register(ShellTool())
        reg.register(HTTPTool())
        reg.register(FileReadTool())
        reg.register(FileWriteTool())
        reg.register(FileEditTool())
        reg.register(WebFetchTool())
        reg.register(WebSearchTool())
        reg.register(GlobTool())
        reg.register(GrepTool())
        reg.register(CoverageTool(self.coverage_store))
        reg.register(AskUserTool())
        reg.register(ConfirmFindingTool())
        if self.skill_registry:
            core_loader = CoreLoadSkillTool(self.skill_registry)
            reg.register(ToolsLoadSkillTool(core_loader))
        return reg

    async def run_interactive(
        self,
        target_info: dict | None = None,
        project_name: str = "",
        source_path: str = "",
        scan_mode: str = "",
        preset: str = "",
        enable_thinking: bool = True,
    ) -> list[dict]:
        system_prompt = build_penetration_system_prompt(
            target_info=target_info,
            project_name=project_name,
            scan_mode=scan_mode,
            preset=preset,
            skill_registry=self.skill_registry,
            coverage_store=self.coverage_store,
            intelligence_store=self.intelligence_store,
            enable_thinking=enable_thinking,
        )

        tool_registry = self._build_registry()

        async def chat_fn(*, messages: list[dict], tools: list[dict] | None = None) -> dict:
            return await self.ai_client._chat_with_tools(
                task_name="penetration_test",
                max_tokens=4096,
                messages=messages,
                tools=tools,
            )

        loop = InteractiveAgentLoop(tool_registry, chat_fn)

        initial_msg = {"role": "user", "content": f"Begin penetration testing of {project_name or source_path or 'the target'}."}

        try:
            history = await loop.run(
                messages=[initial_msg],
                system_prompt=system_prompt,
            )
        except MaxStepsError as exc:
            logger.warning("interactive agent reached max steps: %s", exc)
            history = []

        return history

    async def run(self, penetration_context: dict) -> PenetrationReport:
        runner = getattr(self.ai_client, "run_penetration_test", None)
        if not callable(runner):
            return self._default_report()

        target_info = penetration_context.get("target", {})
        has_tools = hasattr(self.ai_client, "_chat_with_tools")

        if has_tools and penetration_context.get("interactive", False):
            history = await self.run_interactive(
                target_info=target_info,
                project_name=penetration_context.get("project_name", ""),
                source_path=penetration_context.get("source_path", ""),
                scan_mode=penetration_context.get("scan_mode", ""),
                preset=penetration_context.get("preset", ""),
                enable_thinking=getattr(self.ai_client, "enable_thinking", True),
            )
            return self._extract_report_from_history(history)

        return await runner(penetration_context)

    def _extract_report_from_history(self, history: list[dict]) -> PenetrationReport:
        for msg in reversed(history):
            if msg.get("role") == "assistant" and msg.get("content"):
                text = msg["content"]
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict) and "executive_summary" in parsed:
                        return self._normalize_report(parsed)
                except (json.JSONDecodeError, TypeError):
                    continue
        return self._default_report()

    def _normalize_report(self, parsed: dict) -> PenetrationReport:
        benchmark = parsed.get("benchmark", {})
        if not isinstance(benchmark, dict):
            benchmark = {}
        finding_overrides = parsed.get("finding_overrides", [])
        if not isinstance(finding_overrides, list):
            finding_overrides = []

        return {
            "review_note": str(parsed.get("review_note", "")),
            "executive_summary": str(parsed.get("executive_summary", "")),
            "attack_chains": list(parsed.get("attack_chains", [])),
            "reproduction_plan": list(parsed.get("reproduction_plan", [])),
            "analysis_limitations": list(parsed.get("analysis_limitations", [])),
            "next_steps": list(parsed.get("next_steps", [])),
            "benchmark": {
                "findings_covered": int(benchmark.get("findings_covered", 0)),
                "paths_exercised": int(benchmark.get("paths_exercised", 0)),
                "confidence_average": int(benchmark.get("confidence_average", 0)),
                "benchmark_summary": str(benchmark.get("benchmark_summary", "")),
            },
            "finding_overrides": [
                {
                    "file": str(fo.get("file", "")),
                    "line": int(fo.get("line", 0)),
                    "title": str(fo.get("title", "")),
                    "attack_input": str(fo.get("attack_input", "")),
                    "attack_execution": str(fo.get("attack_execution", "")),
                    "attack_result": str(fo.get("attack_result", "")),
                    "explanation": str(fo.get("explanation", "")),
                    "audit_log": list(fo.get("audit_log", [])),
                }
                for fo in finding_overrides[:24] if isinstance(fo, dict)
            ],
        }

    def _default_report(self) -> PenetrationReport:
        return {
            "review_note": "",
            "executive_summary": "",
            "attack_chains": [],
            "reproduction_plan": [],
            "analysis_limitations": [],
            "next_steps": [],
            "benchmark": {
                "findings_covered": 0,
                "paths_exercised": 0,
                "confidence_average": 0,
                "benchmark_summary": "",
            },
            "finding_overrides": [],
        }

    async def learn_from_session(self, history: list[dict], session_id: str | None = None) -> None:
        if not self.intelligence_store:
            return
        text = json.dumps(history, ensure_ascii=False)
        await self.intelligence_store.learn_from_text(text, source_session_id=session_id)
