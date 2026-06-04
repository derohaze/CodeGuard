from __future__ import annotations

from app.infrastructure.ai.tools.base import BaseTool, ToolResult


class AskUserTool(BaseTool):
    name = "ask_user"
    description = "Ask the user a multi-choice question. Use when you need clarification or authorization."
    input_schema = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask the user",
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of answer options (2-8)",
            },
            "allow_custom": {
                "type": "boolean",
                "description": "Whether to allow custom freeform answers",
                "default": False,
            },
        },
        "required": ["question", "options"],
    }
    requires_permission = False

    async def run(self, question: str, options: list[str], allow_custom: bool = False) -> ToolResult:
        return ToolResult.ok(
            f"QUESTION: {question}\n"
            f"OPTIONS: {', '.join(options)}\n"
            f"Response will be provided by the user in the next turn."
        )
