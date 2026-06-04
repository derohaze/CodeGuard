"""Integration tests for InteractiveAgentLoop."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.infrastructure.ai.tools.agent_loop import InteractiveAgentLoop, MaxStepsError, MAX_STEPS
from app.infrastructure.ai.tools.base import ToolResult


class TestAgentLoopConstruction:
    def test_init_stores_deps(self, tool_registry, mock_llm):
        loop = InteractiveAgentLoop(tool_registry, mock_llm)
        assert loop._tools is tool_registry
        assert loop._llm_chat is mock_llm
        assert loop.active_skills == []

    def test_activate_skill(self, tool_registry, mock_llm):
        loop = InteractiveAgentLoop(tool_registry, mock_llm)
        loop.activate_skill("sqli", ["http", "shell"])
        assert loop.active_skills == ["sqli"]
        assert loop._active_skill_tools == [["http", "shell"]]

    def test_activate_skill_dedup(self, tool_registry, mock_llm):
        loop = InteractiveAgentLoop(tool_registry, mock_llm)
        loop.activate_skill("sqli", ["http"])
        loop.activate_skill("sqli", ["shell"])
        assert loop.active_skills == ["sqli"]

    def test_activate_skill_multiple(self, tool_registry, mock_llm):
        loop = InteractiveAgentLoop(tool_registry, mock_llm)
        loop.activate_skill("sqli", ["http"])
        loop.activate_skill("xss", ["shell"])
        assert loop.active_skills == ["sqli", "xss"]


class TestAgentLoopRun:
    @pytest.mark.asyncio
    async def test_immediate_final_message(self, tool_registry):
        """LLM returns final immediately → loop returns after 1 step."""
        mock = AsyncMock(return_value={"role": "assistant", "content": "all done", "type": "final"})
        loop = InteractiveAgentLoop(tool_registry, mock)
        history = await loop.run([{"role": "user", "content": "test"}], system_prompt="be helpful")
        assert len(history) == 3  # system + user + assistant
        assert history[0]["role"] == "system"
        assert history[2]["role"] == "assistant"
        assert history[2]["content"] == "all done"

    @pytest.mark.asyncio
    async def test_single_tool_call_then_final(self, tool_registry):
        """LLM returns tool call, then final → loop executes tool and returns."""
        mock = AsyncMock(side_effect=[
            {
                "role": "assistant",
                "content": "let me check",
                "tool_calls": [
                    {"id": "call_1", "name": "shell", "type": "function", "arguments": '{"command":"echo hi"}'},
                ],
            },
            {"role": "assistant", "content": "done", "type": "final"},
        ])
        loop = InteractiveAgentLoop(tool_registry, mock)
        history = await loop.run([{"role": "user", "content": "run echo hi"}])
        assert len(history) == 4  # user + assistant(toolcall) + tool(result) + assistant(final)
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "tool"
        assert history[2]["name"] == "shell"
        assert history[3]["role"] == "assistant"
        assert history[3]["content"] == "done"

    @pytest.mark.asyncio
    async def test_tool_call_with_dict_args(self, tool_registry):
        """Tool call with parsed dict args (not JSON string) works."""
        mock = AsyncMock(side_effect=[
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_1", "name": "shell", "type": "function", "arguments": {"command": "echo hi"}},
                ],
            },
            {"role": "assistant", "content": "done", "type": "final"},
        ])
        loop = InteractiveAgentLoop(tool_registry, mock)
        history = await loop.run([{"role": "user", "content": "run echo hi"}])
        assert history[2]["role"] == "tool"
        assert "hi" in history[2]["content"]

    @pytest.mark.asyncio
    async def test_tool_call_invalid_json_args_fallback(self, tool_registry):
        """Invalid JSON args string falls back to empty dict gracefully."""
        mock = AsyncMock(side_effect=[
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_1", "name": "shell", "type": "function", "arguments": "{bad json}"},
                ],
            },
            {"role": "assistant", "content": "done", "type": "final"},
        ])
        loop = InteractiveAgentLoop(tool_registry, mock)
        # Should not raise; invalid JSON -> empty args -> shell runs with no command
        history = await loop.run([{"role": "user", "content": "run"}])
        assert history[2]["role"] == "tool"
        # shell with no command may succeed or fail — just verify we got a tool result

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_one_response(self, tool_registry):
        """LLM returns 2 tool calls in one response → both execute."""
        mock = AsyncMock(side_effect=[
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "name": "shell", "type": "function", "arguments": '{"command":"echo a"}',
                     "index": 0},
                    {"id": "c2", "name": "shell", "type": "function", "arguments": '{"command":"echo b"}',
                     "index": 1},
                ],
            },
            {"role": "assistant", "content": "done", "type": "final"},
        ])
        loop = InteractiveAgentLoop(tool_registry, mock)
        history = await loop.run([{"role": "user", "content": "run two commands"}])
        tool_msgs = [m for m in history if m["role"] == "tool"]
        assert len(tool_msgs) == 2

    @pytest.mark.asyncio
    async def test_restricted_tool_blocked_by_skills(self, tool_registry):
        """Tool restricted by active skills → returns fail message."""
        mock = AsyncMock(side_effect=[
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "name": "shell", "type": "function", "arguments": '{"command":"whoami"}'},
                ],
            },
            {"role": "assistant", "content": "done", "type": "final"},
        ])
        loop = InteractiveAgentLoop(tool_registry, mock)
        loop.activate_skill("http_only", ["http"])
        history = await loop.run([{"role": "user", "content": "run shell"}])
        tool_msg = [m for m in history if m["role"] == "tool"][0]
        assert "not allowed" in tool_msg["content"]

    @pytest.mark.asyncio
    async def test_unrestricted_when_no_active_skills(self, tool_registry):
        """No active skills → all tools allowed."""
        mock = AsyncMock(side_effect=[
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "name": "shell", "type": "function", "arguments": '{"command":"whoami"}'},
                ],
            },
            {"role": "assistant", "content": "done", "type": "final"},
        ])
        loop = InteractiveAgentLoop(tool_registry, mock)
        history = await loop.run([{"role": "user", "content": "run shell"}])
        tool_msg = [m for m in history if m["role"] == "tool"][0]
        assert "not allowed" not in tool_msg["content"]

    @pytest.mark.asyncio
    async def test_load_skill_activates_new_skill(self, tool_registry):
        """load_skill tool success → skill is auto-activated."""
        from unittest.mock import MagicMock
        from app.infrastructure.ai.tools.load_skill_tool import LoadSkillTool
        from app.infrastructure.skills.loader import LoadSkillTool as CoreLoader

        mock_loader = MagicMock(spec=CoreLoader)
        mock_loader.execute = AsyncMock(return_value="# SSRF Skill Playbook\n\nmethodology...")
        load_tool = LoadSkillTool(loader=mock_loader)
        tool_registry.register(load_tool)

        mock = AsyncMock(side_effect=[
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "name": "load_skill",
                        "type": "function",
                        "arguments": '{"name":"ssrf"}',
                    },
                ],
            },
            {"role": "assistant", "content": "done", "type": "final"},
        ])
        loop = InteractiveAgentLoop(tool_registry, mock)

        loop._handle_skill_activation = lambda args: loop.activate_skill(
            args.get("name", ""), ["http", "shell"]
        )

        history = await loop.run([{"role": "user", "content": "load ssrf skill"}])
        assert "ssrf" in loop.active_skills

    @pytest.mark.asyncio
    async def test_max_steps_raises_error(self, tool_registry):
        """LLM keeps making tool calls → eventually MaxStepsError."""
        mock = AsyncMock(return_value={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "c1", "name": "shell", "type": "function", "arguments": '{"command":"echo a"}'},
            ],
        })
        loop = InteractiveAgentLoop(tool_registry, mock)
        with pytest.raises(MaxStepsError, match=str(MAX_STEPS)):
            await loop.run([{"role": "user", "content": "loop forever"}])

    @pytest.mark.asyncio
    async def test_unknown_tool_name_handled(self, tool_registry):
        """LLM calls tool that doesn't exist → fail result, no crash."""
        mock = AsyncMock(side_effect=[
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "name": "nonexistent_tool", "type": "function", "arguments": "{}"},
                ],
            },
            {"role": "assistant", "content": "done", "type": "final"},
        ])
        loop = InteractiveAgentLoop(tool_registry, mock)
        history = await loop.run([{"role": "user", "content": "call bad tool"}])
        tool_msg = [m for m in history if m["role"] == "tool"][0]
        assert "unknown" in tool_msg["content"]


class TestAgentLoopParsing:
    def test_parse_response_dict(self, tool_registry, mock_llm):
        loop = InteractiveAgentLoop(tool_registry, mock_llm)
        result = loop._parse_response({"role": "assistant", "content": "hello"})
        assert result == {"role": "assistant", "content": "hello"}

    def test_parse_response_string(self, tool_registry, mock_llm):
        loop = InteractiveAgentLoop(tool_registry, mock_llm)
        result = loop._parse_response("hello")
        assert result == {"role": "assistant", "content": "hello"}

    def test_has_tool_calls_true(self, tool_registry, mock_llm):
        loop = InteractiveAgentLoop(tool_registry, mock_llm)
        assert loop._has_tool_calls({"tool_calls": [{"id": "1"}]}) is True

    def test_has_tool_calls_false(self, tool_registry, mock_llm):
        loop = InteractiveAgentLoop(tool_registry, mock_llm)
        assert loop._has_tool_calls({}) is False
        assert loop._has_tool_calls({"tool_calls": []}) is False


class TestToolRestrictionEdgeCases:
    @pytest.mark.asyncio
    async def test_block_tool_then_allow(self, tool_registry):
        """Tool name alias resolution works in restriction context."""
        mock = AsyncMock(side_effect=[
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "name": "BashTool", "type": "function", "arguments": '{"command":"whoami"}'},
                ],
            },
            {"role": "assistant", "content": "done", "type": "final"},
        ])
        loop = InteractiveAgentLoop(tool_registry, mock)
        loop.activate_skill("http_only", ["http"])
        history = await loop.run([{"role": "user", "content": "run shell"}])
        tool_msg = [m for m in history if m["role"] == "tool"][0]
        assert "not allowed" in tool_msg["content"]
