from __future__ import annotations

from app.infrastructure.ai.tools.base import BaseTool, ToolResult
from app.infrastructure.coverage.store import CoverageStore


class CoverageTool(BaseTool):
    name = "coverage"
    description = "Track penetration test coverage. Mark tested endpoints, list coverage, find untested areas, get summary, or clear."
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["mark", "list", "untested", "summary", "clear"],
                "description": "Action to perform",
            },
            "endpoint": {
                "type": "string",
                "description": "Endpoint URL (required for mark)",
            },
            "param": {
                "type": "string",
                "description": "Parameter name (required for mark)",
            },
            "vuln_class": {
                "type": "string",
                "description": "Vulnerability class (required for mark)",
            },
            "status": {
                "type": "string",
                "enum": ["tried", "passed", "failed", "waf-blocked", "skipped"],
                "description": "Test status (default: tried)",
            },
            "notes": {
                "type": "string",
                "description": "Optional notes about the test",
            },
        },
        "required": ["action"],
    }

    def __init__(self, store: CoverageStore | None = None):
        super().__init__()
        self._store = store

    async def run(
        self,
        action: str,
        endpoint: str = "",
        param: str = "",
        vuln_class: str = "",
        status: str = "tried",
        notes: str | None = None,
    ) -> ToolResult:
        if not self._store:
            return ToolResult.fail("coverage store not available")

        if action == "mark":
            if not endpoint or not param or not vuln_class:
                return ToolResult.fail("mark requires endpoint, param, and vuln_class")
            entry = self._store.mark(endpoint, param, vuln_class, status, notes)
            return ToolResult.ok(f"marked: {entry.endpoint} | {entry.param} | {entry.vuln_class} | {entry.status}")

        if action == "list":
            entries = self._store.list()
            if not entries:
                return ToolResult.ok("no coverage entries")
            lines = [f"{e.endpoint} | {e.param} | {e.vuln_class} | {e.status} | count={e.count}" for e in entries]
            return ToolResult.ok("\n".join(lines))

        if action == "untested":
            return ToolResult.ok("use untested with candidates and vuln_classes array")

        if action == "summary":
            s = self._store.summary()
            return ToolResult.ok(
                f"total: {s.total}\nby status: {dict(s.by_status)}\nby vuln_class: {dict(s.by_vuln_class)}"
            )

        if action == "clear":
            self._store.clear()
            return ToolResult.ok("coverage cleared")

        return ToolResult.fail(f"unknown action: {action}")
