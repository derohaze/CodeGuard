from __future__ import annotations

import os

from app.infrastructure.ai.tools.base import BaseTool, ToolResult
from app.infrastructure.ai.tools.restriction import is_sensitive_path

MAX_READ_CHARS = 204800


class FileReadTool(BaseTool):
    name = "file_read"
    description = "Read the contents of a file. Max 200KB."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file",
            },
        },
        "required": ["path"],
    }
    requires_permission = True

    async def run(self, path: str) -> ToolResult:
        expanded = os.path.expanduser(path)
        expanded = os.path.abspath(expanded)
        if is_sensitive_path(expanded):
            return ToolResult.fail(f"cannot read sensitive path: {path}")
        if not os.path.isfile(expanded):
            return ToolResult.fail(f"file not found: {path}")
        try:
            with open(expanded, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(MAX_READ_CHARS + 1)
            if len(content) > MAX_READ_CHARS:
                content = content[:MAX_READ_CHARS] + f"\n... (truncated at {MAX_READ_CHARS} chars)"
            return ToolResult.ok(content)
        except Exception as exc:
            return ToolResult.fail(f"read error: {exc}")


class FileWriteTool(BaseTool):
    name = "file_write"
    description = "Write content to a file. Creates parent directories if needed."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file",
            },
            "content": {
                "type": "string",
                "description": "Content to write",
            },
        },
        "required": ["path", "content"],
    }
    requires_permission = True

    async def run(self, path: str, content: str) -> ToolResult:
        expanded = os.path.expanduser(path)
        expanded = os.path.abspath(expanded)
        if is_sensitive_path(expanded):
            return ToolResult.fail(f"cannot write to sensitive path: {path}")
        try:
            directory = os.path.dirname(expanded)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(expanded, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult.ok(f"wrote {len(content)} bytes to {path}")
        except Exception as exc:
            return ToolResult.fail(f"write error: {exc}")


class FileEditTool(BaseTool):
    name = "file_edit"
    description = "Edit a file using string replacement. Replaces first occurrence of old_string with new_string."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file",
            },
            "old_string": {
                "type": "string",
                "description": "Text to find and replace",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement text",
            },
        },
        "required": ["path", "old_string", "new_string"],
    }
    requires_permission = True

    async def run(self, path: str, old_string: str, new_string: str) -> ToolResult:
        expanded = os.path.expanduser(path)
        expanded = os.path.abspath(expanded)
        if is_sensitive_path(expanded):
            return ToolResult.fail(f"cannot edit sensitive path: {path}")
        try:
            with open(expanded, "r", encoding="utf-8") as f:
                content = f.read()
            if old_string not in content:
                return ToolResult.fail(f"old_string not found in {path}")
            new_content = content.replace(old_string, new_string, 1)
            with open(expanded, "w", encoding="utf-8") as f:
                f.write(new_content)
            replaced_count = content.count(old_string)
            extra = f" ({replaced_count - 1} additional occurrences not replaced)" if replaced_count > 1 else ""
            return ToolResult.ok(f"replaced 1 occurrence in {path}{extra}")
        except Exception as exc:
            return ToolResult.fail(f"edit error: {exc}")
