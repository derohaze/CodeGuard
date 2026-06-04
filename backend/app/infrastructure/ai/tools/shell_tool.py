from __future__ import annotations

import asyncio
import re

from app.infrastructure.ai.tools.base import BaseTool, ToolResult

DENY_COMMANDS: list[re.Pattern] = [
    re.compile(r"\brm\s+-rf\s+/\s*$"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\s+of=/dev/"),
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"\bpoweroff\b"),
    re.compile(r"\binit\s+0\b"),
    re.compile(r"\binit\s+6\b"),
    re.compile(r":\(\)\s*\{"),
    re.compile(r"\bwget\s+.*\||\bcurl\s+.*\||\bbash\s+<"),
]

MAX_OUTPUT_CHARS = 32768
DEFAULT_TIMEOUT = 300
MAX_TIMEOUT = 1800


class ShellTool(BaseTool):
    name = "shell"
    description = "Run a shell command. Uses cmd.exe on Windows, /bin/sh on Unix."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": f"Timeout in seconds (default {DEFAULT_TIMEOUT}, max {MAX_TIMEOUT})",
                "default": DEFAULT_TIMEOUT,
            },
            "description": {
                "type": "string",
                "description": "Human-readable description of what this command does",
            },
        },
        "required": ["command"],
    }
    requires_permission = True

    async def run(self, command: str, timeout: int = DEFAULT_TIMEOUT, description: str = "") -> ToolResult:
        for pattern in DENY_COMMANDS:
            if pattern.search(command):
                return ToolResult.fail(f"command denied by security policy: matches {pattern.pattern}")
        safe_timeout = max(1, min(timeout, MAX_TIMEOUT))
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=safe_timeout
            )
        except asyncio.TimeoutError:
            return ToolResult.fail(f"command timed out after {safe_timeout}s")
        except Exception as exc:
            return ToolResult.fail(f"execution error: {exc}")

        out = stdout.decode("utf-8", errors="replace") if stdout else ""
        err = stderr.decode("utf-8", errors="replace") if stderr else ""

        if len(out) > MAX_OUTPUT_CHARS:
            out = out[:MAX_OUTPUT_CHARS] + f"\n... (truncated at {MAX_OUTPUT_CHARS} chars)"

        result = f"exit code: {proc.returncode}\n"
        if out:
            result += f"\nstdout:\n{out}\n"
        if err:
            result += f"\nstderr:\n{err}\n"

        return ToolResult.ok(result)
