from __future__ import annotations

import logging
from typing import Any

from app.infrastructure.ai.tools.base import BaseTool, ToolResult
from app.infrastructure.ai.tools.restriction import is_tool_allowed

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError("tool must have a name")
        self._tools[tool.name] = tool
        logger.debug("registered tool: %s", tool.name)

    def register_many(self, *tools: BaseTool) -> None:
        for t in tools:
            self.register(t)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list(self) -> list[BaseTool]:
        return list(self._tools.values())

    def to_openai_tools(self) -> list[dict[str, Any]]:
        return [t.to_openai_function() for t in self._tools.values()]

    async def execute(
        self,
        name: str,
        args: dict[str, Any] | None = None,
        active_skill_tools: list[list[str]] | None = None,
    ) -> ToolResult:
        if not is_tool_allowed(name, active_skill_tools):
            return ToolResult.fail(
                f'tool "{name}" is not allowed by the currently active skills'
            )
        tool = self._tools.get(name)
        if not tool:
            return ToolResult.fail(f'unknown tool "{name}"')
        unexpected_args = _unexpected_tool_args(tool, args or {})
        if unexpected_args:
            allowed_args = ", ".join(sorted((tool.input_schema.get("properties") or {}).keys()))
            return ToolResult.fail(
                f'tool "{name}" received unexpected argument(s): {", ".join(unexpected_args)}. '
                f"Allowed arguments: {allowed_args or 'none'}"
            )
        try:
            return await tool.run(**(args or {}))
        except Exception as exc:
            logger.exception("tool %s failed", name)
            return ToolResult.fail(f"{type(exc).__name__}: {exc}")


def _unexpected_tool_args(tool: BaseTool, args: dict[str, Any]) -> list[str]:
    schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
    if schema.get("type") != "object" or schema.get("additionalProperties") is True:
        return []
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []
    allowed = {str(key) for key in properties}
    return sorted(str(key) for key in args if str(key) not in allowed)
