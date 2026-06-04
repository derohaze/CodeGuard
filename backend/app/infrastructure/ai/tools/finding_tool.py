from __future__ import annotations

from app.infrastructure.ai.tools.base import BaseTool, ToolResult


class ConfirmFindingTool(BaseTool):
    name = "confirm_finding"
    description = "Record a confirmed vulnerability finding with evidence."
    input_schema = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short title for the finding",
            },
            "severity": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low", "info"],
                "description": "Severity level",
            },
            "endpoint": {
                "type": "string",
                "description": "Affected URL or endpoint",
            },
            "parameter": {
                "type": "string",
                "description": "Affected parameter, if applicable",
            },
            "description": {
                "type": "string",
                "description": "Detailed description of the vulnerability",
            },
            "impact": {
                "type": "string",
                "description": "Business/security impact",
            },
            "remediation": {
                "type": "string",
                "description": "Recommended fix",
            },
            "evidence": {
                "type": "string",
                "description": "Evidence showing the vulnerability (request/response, output, etc.)",
            },
        },
        "required": ["title", "severity", "endpoint", "description"],
    }
    requires_permission = False

    async def run(
        self,
        title: str,
        severity: str,
        endpoint: str,
        parameter: str = "",
        description: str = "",
        impact: str = "",
        remediation: str = "",
        evidence: str = "",
    ) -> ToolResult:
        slug = title.lower().replace(" ", "-").replace("/", "-")[:60]
        report = (
            f"# {title}\n\n"
            f"- **Severity**: {severity}\n"
            f"- **Endpoint**: {endpoint}\n"
            f"- **Parameter**: {parameter}\n\n"
            f"## Description\n{description}\n\n"
        )
        if impact:
            report += f"## Impact\n{impact}\n\n"
        if remediation:
            report += f"## Remediation\n{remediation}\n\n"
        if evidence:
            report += f"## Evidence\n```\n{evidence}\n```\n"

        return ToolResult.ok(f"Finding '{slug}' confirmed.\n\n{report}")
