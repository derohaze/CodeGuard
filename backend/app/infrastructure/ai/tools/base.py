from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: str | None = None

    @classmethod
    def ok(cls, output: str = "") -> ToolResult:
        return cls(success=True, output=output)

    @classmethod
    def fail(cls, error: str) -> ToolResult:
        return cls(success=False, error=error)


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {}
    requires_permission: bool = False

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
        )

    def to_openai_function(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    @abstractmethod
    async def run(self, **kwargs) -> ToolResult:
        ...
