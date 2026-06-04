from __future__ import annotations

"""Aegix penetration testing benchmark framework.

Measures agent performance across:
- Findings discovered (vs ground truth)
- Execution time
- Coverage achieved
- Confidence scores
- Tool call efficiency
- Report quality

Usage:
    from benchmark.runner import BenchmarkRunner
    runner = BenchmarkRunner()
    results = await runner.run(target_url="http://127.0.0.1:9000")
    runner.print_table()
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add backend to path for importing agent infrastructure
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ─── Known vulnerabilities in the benchmark target ──────────────────────
# Update this if the target changes.

GROUND_TRUTH: dict[str, dict] = {
    "sql_injection_search": {
        "id": "V001",
        "title": "SQL Injection in user search",
        "endpoint": "GET /api/users?search=",
        "severity": "critical",
        "category": "Injection",
    },
    "nosql_injection_login": {
        "id": "V002",
        "title": "NoSQL Injection in login",
        "endpoint": "POST /api/auth/login",
        "severity": "critical",
        "category": "Injection",
    },
    "idor_user_profile": {
        "id": "V003",
        "title": "IDOR in user profile endpoint",
        "endpoint": "GET /api/users/{user_id}",
        "severity": "high",
        "category": "Broken Access Control",
    },
    "path_traversal": {
        "id": "V004",
        "title": "Path traversal in file endpoint",
        "endpoint": "GET /api/files/{filename}",
        "severity": "high",
        "category": "Injection",
    },
    "stored_xss": {
        "id": "V005",
        "title": "Stored XSS in feedback",
        "endpoint": "POST /api/feedback",
        "severity": "medium",
        "category": "XSS",
    },
    "weak_password_policy": {
        "id": "V006",
        "title": "Weak password policy",
        "endpoint": "POST /api/auth/register",
        "severity": "medium",
        "category": "Cryptographic Failure",
    },
    "no_rate_limit": {
        "id": "V007",
        "title": "No rate limiting on login",
        "endpoint": "POST /api/auth/login",
        "severity": "low",
        "category": "Security Misconfiguration",
    },
    "info_disclosure": {
        "id": "V008",
        "title": "Information disclosure in errors",
        "endpoint": "General",
        "severity": "low",
        "category": "Information Disclosure",
    },
    "mass_assignment": {
        "id": "V009",
        "title": "Mass assignment in user update",
        "endpoint": "PUT /api/users/{user_id}",
        "severity": "high",
        "category": "Broken Access Control",
    },
    "open_redirect": {
        "id": "V010",
        "title": "Open redirect",
        "endpoint": "GET /api/redirect",
        "severity": "low",
        "category": "Injection",
    },
}


@dataclass
class BenchmarkRunResult:
    label: str  # "before" or "after"
    timestamp: str
    total_time_seconds: float
    findings_count: int
    findings_details: list[dict]
    severity_counts: dict[str, int]
    coverage_total: int
    coverage_tested: int
    avg_confidence: float
    steps_used: int
    tool_calls: int
    missed_findings: list[str]
    false_positives: list[str]
    recall: float  # findings found / total ground truth
    precision: float  # true positives / (true positives + false positives)
    report_quality_score: float  # 0-1, based on report structure completeness


class BenchmarkRunner:
    def __init__(self, ground_truth: dict | None = None):
        self.ground_truth = ground_truth or GROUND_TRUTH
        self.results: list[BenchmarkRunResult] = []

    async def run(
        self,
        *,
        label: str,
        target_url: str = "http://127.0.0.1:9000",
        agent_class_path: str = "app.infrastructure.ai.agents.penetration_tester.agent.PenetrationTestAgent",
        use_stashed_prompts: bool = False,
        timeout_seconds: int = 300,
    ) -> BenchmarkRunResult:
        """Run the penetration agent against target_url and collect metrics.

        Args:
            label: Label for this run ("before" or "after").
            target_url: Base URL of the vulnerable test API.
            agent_class_path: Dotted path to the agent class.
            use_stashed_prompts: If True, temporarily restore old prompts from git.
            timeout_seconds: Max time before aborting.
        """
        start = time.monotonic()

        # Stash/restore prompts if benchmarking before/after
        if use_stashed_prompts:
            self._stash_current_prompts()
            self._restore_git_prompts()

        try:
            # Import and run the agent
            from app.infrastructure.ai.agents.penetration_tester.agent import PenetrationTestAgent
            from app.infrastructure.ai.nvidia_security_client import NvidiaSecurityClient
            from app.core.config import get_settings

            settings = get_settings()
            ai_client = NvidiaSecurityClient()
            if not ai_client.is_configured(settings):
                raise RuntimeError("NVIDIA_API_KEY not configured. Cannot run benchmark without AI credentials.")

            agent = PenetrationTestAgent(ai_client=ai_client)

            target_info = {"url": target_url}
            penetration_context = {
                "project_name": "benchmark-vuln-api",
                "source_path": str(Path(__file__).resolve().parent / "vuln_api.py"),
                "target": target_info,
                "interactive": True,
                "preset": "full",
                "scan_mode": "dynamic",
                "session_id": f"benchmark-{label}-{int(time.time())}",
            }

            # Run the agent
            history = await agent.run(penetration_context)

            # Parse findings from history
            findings = self._extract_findings(history)

            # Calculate metrics
            elapsed = time.monotonic() - start
            result = self._compute_result(label, findings, elapsed, history)
            self.results.append(result)
            return result

        finally:
            if use_stashed_prompts:
                self._restore_stashed_prompts()

    def _extract_findings(self, history: list[dict]) -> list[dict]:
        """Extract confirmed findings from agent history."""
        findings = []
        for msg in history:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content", "")
            if isinstance(content, str):
                # Try to parse JSON report
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        if "finding_overrides" in parsed:
                            findings.extend(parsed["finding_overrides"])
                        if "findings" in parsed:
                            findings.extend(parsed["findings"])
                except (json.JSONDecodeError, TypeError):
                    pass

            # Also check tool results for confirm_finding
            tool_calls = msg.get("tool_calls", [])
            if not isinstance(tool_calls, list):
                continue
            for tc in tool_calls:
                fn = tc.get("function", {})
                if fn.get("name") == "confirm_finding":
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                        findings.append(args)
                    except (json.JSONDecodeError, TypeError):
                        pass
        return findings

    def _compute_result(
        self, label: str, findings: list[dict], elapsed: float, history: list[dict]
    ) -> BenchmarkRunResult:
        # Count ground truth matches
        true_positives = set()
        false_positives = []
        found_titles = set()

        for f in findings:
            title = (f.get("title") or f.get("summary") or "").lower()
            found_titles.add(title)

            matched = False
            for gk, gv in self.ground_truth.items():
                gt_title = gv["title"].lower()
                gt_id = gv["id"].lower()
                if gt_id in title or any(w in title for w in gt_title.split()):
                    true_positives.add(gk)
                    matched = True
                    break
            if not matched:
                false_positives.append(title)

        missed = set(self.ground_truth.keys()) - true_positives
        recall = len(true_positives) / len(self.ground_truth) if self.ground_truth else 0
        precision = len(true_positives) / (len(true_positives) + len(false_positives)) if (true_positives or false_positives) else 0

        # Severity distribution
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in findings:
            sev = (f.get("severity") or "").lower()
            if sev in severity_counts:
                severity_counts[sev] += 1

        # Steps and tool calls
        dict_history = [m for m in history if isinstance(m, dict)]
        steps_used = len([m for m in dict_history if m.get("role") == "assistant"])
        tool_calls = sum(
            len(m.get("tool_calls", []) or [])
            for m in dict_history
            if m.get("role") == "assistant"
        )

        # Average confidence
        confidences = [int(f.get("confidence", 0)) for f in findings if f.get("confidence")]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        # Coverage
        coverage_total = len(self.ground_truth)
        coverage_tested = len(true_positives)

        # Report quality (simplified: check if executive summary, steps, etc.)
        report_quality = 0.0
        for msg in reversed(dict_history):
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > 200:
                quality_score = 0
                for keyword in ["executive summary", "finding", "impact", "reproduction", "remediation", "endpoint"]:
                    if keyword.lower() in content.lower():
                        quality_score += 1 / 6
                report_quality = min(quality_score, 1.0)
                break

        return BenchmarkRunResult(
            label=label,
            timestamp=datetime.utcnow().isoformat(),
            total_time_seconds=round(elapsed, 2),
            findings_count=len(findings),
            findings_details=findings[:20],
            severity_counts=severity_counts,
            coverage_total=coverage_total,
            coverage_tested=coverage_tested,
            avg_confidence=round(avg_conf, 1),
            steps_used=steps_used,
            tool_calls=tool_calls,
            missed_findings=[self.ground_truth[m]["title"] for m in sorted(missed)],
            false_positives=[fp[:80] for fp in false_positives],
            recall=round(recall * 100, 1),
            precision=round(precision * 100, 1),
            report_quality_score=round(report_quality, 2),
        )

    def print_table(self) -> str:
        """Print a before/after comparison table."""
        if len(self.results) < 2:
            return "Need at least 2 runs (before + after) for comparison."

        before = self.results[0]
        after = self.results[1]

        lines = [
            "=" * 80,
            "  AEGIX PENETRATION TESTING BENCHMARK",
            f"  Ran: {before.timestamp}",
            "=" * 80,
            "",
            f"  {'Metric':<36} {'Before':<12} {'After':<12} {'Change':<12}",
            f"  {'-'*36} {'-'*12} {'-'*12} {'-'*12}",
        ]

        metrics = [
            ("Total time (s)", f"{before.total_time_seconds}", f"{after.total_time_seconds}"),
            ("Findings discovered", f"{before.findings_count}", f"{after.findings_count}"),
            ("True positives", f"{before.coverage_tested}", f"{after.coverage_tested}"),
            ("Recall (%)", f"{before.recall}%", f"{after.recall}%"),
            ("Precision (%)", f"{before.precision}%", f"{after.precision}%"),
            ("Average confidence", f"{before.avg_confidence}", f"{after.avg_confidence}"),
            ("Steps used", f"{before.steps_used}", f"{after.steps_used}"),
            ("Tool calls", f"{before.tool_calls}", f"{after.tool_calls}"),
            ("Report quality", f"{before.report_quality_score}", f"{after.report_quality_score}"),
        ]

        for name, b_val, a_val in metrics:
            try:
                b_num = float(b_val)
                a_num = float(a_val)
                diff = a_num - b_num
                if abs(diff) < 0.01:
                    change = "—"
                else:
                    pct = (diff / b_num * 100) if b_num != 0 else 0
                    arrow = "↑" if diff > 0 else "↓"
                    change = f"{arrow} {abs(pct):.1f}%"
            except (ValueError, TypeError):
                change = "—"
            lines.append(f"  {name:<36} {b_val:<12} {a_val:<12} {change:<12}")

        if before.missed_findings or after.missed_findings:
            lines.extend([
                "",
                "  ── Missed findings ──",
                f"  Before missed: {', '.join(before.missed_findings[:5]) if before.missed_findings else 'none'}",
                f"  After missed:  {', '.join(after.missed_findings[:5]) if after.missed_findings else 'none'}",
            ])

        if before.false_positives or after.false_positives:
            lines.extend([
                "",
                "  ── False positives ──",
                f"  Before: {len(before.false_positives)} — {', '.join(before.false_positives[:3]) if before.false_positives else 'none'}",
                f"  After:  {len(after.false_positives)} — {', '.join(after.false_positives[:3]) if after.false_positives else 'none'}",
            ])

        lines.extend([
            "",
            "  ── Severity distribution ──",
            f"  {'Severity':<12} {'Before':<10} {'After':<10}",
            f"  {'-'*12} {'-'*10} {'-'*10}",
        ])
        for sev in ["critical", "high", "medium", "low"]:
            lines.append(f"  {sev:<12} {before.severity_counts.get(sev, 0):<10} {after.severity_counts.get(sev, 0):<10}")

        lines.extend([
            "",
            "=" * 80,
            f"  Ground truth: {len(self.ground_truth)} known vulnerabilities",
            "=" * 80,
        ])

        table = "\n".join(lines)

        # Also save to file
        report_path = Path(__file__).resolve().parent.parent / "artifacts" / "benchmark-report.txt"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(table, encoding="utf-8")
        print(table)

        return table

    def _prompts_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "app" / "infrastructure" / "ai" / "prompts"

    def _stash_path(self) -> Path:
        p = self._prompts_dir().parent / ".benchmark_stash"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _stash_current_prompts(self) -> None:
        import shutil
        stash = self._stash_path()
        prompts_dir = self._prompts_dir()
        if stash.exists():
            shutil.rmtree(stash)
        shutil.copytree(prompts_dir, stash)

    def _restore_git_prompts(self) -> None:
        """Restore prompt files from git HEAD (before our changes)."""
        import subprocess
        prompts_dir = self._prompts_dir()
        for md_file in prompts_dir.glob("*.md"):
            rel = md_file.relative_to(Path.cwd()).as_posix()
            result = subprocess.run(
                ["git", "show", f"HEAD:{rel}"],
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )
            if result.returncode == 0:
                md_file.write_text(result.stdout, encoding="utf-8")

    def _restore_stashed_prompts(self) -> None:
        import shutil
        stash = self._stash_path()
        prompts_dir = self._prompts_dir()
        if prompts_dir.exists():
            shutil.rmtree(prompts_dir)
        if stash.exists():
            shutil.copytree(stash, prompts_dir)
            shutil.rmtree(stash)
