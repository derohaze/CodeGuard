from __future__ import annotations

from app.infrastructure.ai.tools.base import BaseTool, ToolResult
from app.infrastructure.skills.loader import LoadSkillTool as CoreLoadSkillTool


class LoadSkillTool(BaseTool):
    name = "load_skill"
    description = "Load a skill playbook. Run this before testing a specific vulnerability class to get detailed methodology."
    input_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Skill name to load (e.g. jwt, ssrf, recon, webvuln)",
            },
        },
        "required": ["name"],
    }
    requires_permission = False

    def __init__(self, loader: CoreLoadSkillTool | None = None):
        super().__init__()
        self._loader = loader

    async def run(self, name: str) -> ToolResult:
        if not self._loader:
            return ToolResult.fail("skill loader not available")
        try:
            body = await self._loader.execute(name)
            return ToolResult.ok(body)
        except ValueError as exc:
            return ToolResult.fail(str(exc))
