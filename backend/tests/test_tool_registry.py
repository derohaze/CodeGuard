"""Tests for ToolRegistry."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.infrastructure.ai.tools.base import BaseTool, ToolResult
from app.infrastructure.ai.tools.registry import ToolRegistry


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = _make_tool("test_tool")
        reg.register(tool)
        assert reg.get("test_tool") is tool

    def test_register_many(self):
        reg = ToolRegistry()
        t1, t2 = _make_tool("t1"), _make_tool("t2")
        reg.register_many(t1, t2)
        assert len(reg.list()) == 2

    def test_get_nonexistent(self):
        reg = ToolRegistry()
        assert reg.get("nope") is None

    def test_list(self):
        reg = ToolRegistry()
        assert reg.list() == []
        reg.register(_make_tool("a"))
        assert len(reg.list()) == 1

    def test_to_openai_tools(self):
        reg = ToolRegistry()
        reg.register(_make_tool("foo"))
        tools = reg.to_openai_tools()
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "foo"

    @pytest.mark.asyncio
    async def test_execute_found(self):
        reg = ToolRegistry()
        tool = _make_tool("greet")
        tool.run = AsyncMock(return_value=ToolResult.ok("hello"))  # type: ignore
        reg.register(tool)
        result = await reg.execute("greet")
        assert result.success
        assert result.output == "hello"

    @pytest.mark.asyncio
    async def test_execute_not_found(self):
        reg = ToolRegistry()
        result = await reg.execute("gone")
        assert not result.success
        assert "unknown" in (result.error or "")

    @pytest.mark.asyncio
    async def test_execute_restricted(self):
        reg = ToolRegistry()
        reg.register(_make_tool("secret"))
        result = await reg.execute("secret", active_skill_tools=[["http"]])
        assert not result.success
        assert "not allowed" in (result.error or "")

    @pytest.mark.asyncio
    async def test_execute_exception_caught(self):
        reg = ToolRegistry()
        bad = _make_tool("crash")
        bad.run = AsyncMock(side_effect=ValueError("boom"))  # type: ignore
        reg.register(bad)
        result = await reg.execute("crash")
        assert not result.success
        assert "ValueError" in (result.error or "")

    def test_register_empty_name_raises(self):
        reg = ToolRegistry()
        with pytest.raises(ValueError, match="must have a name"):
            reg.register(_make_tool(""))


def _make_tool(name: str) -> BaseTool:
    async def run_fn(**_kwargs) -> ToolResult:
        return ToolResult.ok(name)

    return type(
        "FakeTool",
        (BaseTool,),
        {
            "name": name,
            "description": f"tool {name}",
            "input_schema": {"type": "object", "properties": {}},
            "run": run_fn,
        },
    )()
