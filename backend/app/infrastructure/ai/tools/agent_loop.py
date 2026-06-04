from __future__ import annotations

import json
import logging
from typing import Any

from app.infrastructure.ai.tools.base import ToolResult
from app.infrastructure.ai.tools.registry import ToolRegistry
from app.infrastructure.ai.tools.restriction import is_tool_allowed
from app.infrastructure.ai.tools.load_skill_tool import LoadSkillTool

logger = logging.getLogger(__name__)


MAX_STEPS = 25
TOOL_CALL_TIMEOUT = 120


class AgentLoopError(Exception):
    ...


class MaxStepsError(AgentLoopError):
    def __init__(self, steps: int):
        super().__init__(f"agent reached max steps ({steps})")


class InteractiveAgentLoop:
    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_chat_fn,
    ):
        self._tools = tool_registry
        self._llm_chat = llm_chat_fn
        self._active_skills: list[str] = []
        self._active_skill_tools: list[list[str]] = []

    @property
    def active_skills(self) -> list[str]:
        return list(self._active_skills)

    def activate_skill(self, name: str, allowed_tools: list[str]) -> None:
        if name not in self._active_skills:
            self._active_skills.append(name)
            self._active_skill_tools.append(allowed_tools)

    async def run(self, messages: list[dict], system_prompt: str = "") -> list[dict]:
        history: list[dict] = list(messages)
        if system_prompt:
            history.insert(0, {"role": "system", "content": system_prompt})

        for step in range(1, MAX_STEPS + 1):
            response = await self._llm_chat(
                messages=history,
                tools=self._tools.to_openai_tools(),
            )

            msg = self._parse_response(response)
            history.append(msg)

            if msg.get("type") == "final" or not self._has_tool_calls(msg):
                return history

            for tc in self._get_tool_calls(msg):
                if not is_tool_allowed(tc["name"], self._active_skill_tools):
                    result = ToolResult.fail(
                        f'tool "{tc["name"]}" is not allowed by active skills'
                    )
                else:
                    result = await self._execute_tool_call(tc)

                history.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tc["name"],
                    "content": result.output if result.success else result.error or "error",
                })

                if tc["name"] == "load_skill" and result.success:
                    self._handle_skill_activation(tc.get("arguments", {}))

        raise MaxStepsError(MAX_STEPS)

    def _parse_response(self, response: Any) -> dict:
        if isinstance(response, dict):
            return response
        return {"role": "assistant", "content": str(response)}

    def _has_tool_calls(self, msg: dict) -> bool:
        return bool(msg.get("tool_calls"))

    def _get_tool_calls(self, msg: dict) -> list[dict]:
        return msg.get("tool_calls", [])

    async def _execute_tool_call(self, tc: dict) -> ToolResult:
        name = tc.get("name", "")
        args_raw = tc.get("arguments", tc.get("args", "{}"))
        if isinstance(args_raw, str):
            try:
                args = json.loads(args_raw)
            except json.JSONDecodeError:
                args = {}
        else:
            args = args_raw or {}
        return await self._tools.execute(name, args, self._active_skill_tools)

    def _handle_skill_activation(self, args: dict) -> None:
        name = args.get("name", "")
        tool = self._tools.get(name)
        if tool:
            self.activate_skill(name, tool.input_schema.get("allowed-tools", []))
