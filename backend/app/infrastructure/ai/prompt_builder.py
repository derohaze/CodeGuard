from __future__ import annotations

from app.infrastructure.skills.registry import SkillRegistry
from app.infrastructure.coverage.store import CoverageStore
from app.infrastructure.intelligence.continuous.store import IntelligenceStore


def build_penetration_system_prompt(
    target_info: dict | None = None,
    project_name: str = "",
    scan_mode: str = "",
    preset: str = "",
    skill_registry: SkillRegistry | None = None,
    coverage_store: CoverageStore | None = None,
    intelligence_store: IntelligenceStore | None = None,
    enable_thinking: bool = True,
) -> str:
    sections: list[str] = []

    profile = "full"
    sections.append(_identity_section(profile))
    sections.append(_objective_section())

    if target_info:
        sections.append(_target_section(target_info, project_name, scan_mode, preset))

    sections.append(_approach_section())

    if skill_registry:
        sections.append(_skills_section(skill_registry))

    if coverage_store:
        sections.append(_coverage_section(coverage_store))

    if intelligence_store and target_info:
        sections.append(_intelligence_section(intelligence_store, target_info))

    sections.append(_tool_usage_section())
    sections.append(_report_format_section())

    if not enable_thinking:
        sections.append(_no_thinking_section())

    return "\n\n".join(sections)


SYSTEM_IDENTITY_FULL = """You are Aegix, an expert web and API security testing agent.

You have deep knowledge of:
- OWASP Top 10 (2021)
- API Security Top 10
- LLM AI Security Top 10
- Bugcrowd VRT (Vulnerability Rating Taxonomy)
- PortSwigger research and web security techniques
- Web3 / blockchain security patterns when relevant

Approach every engagement with a creative, tenacious hunter mindset.
Chain multiple low-severity issues together to demonstrate real impact.
Always verify findings with concrete evidence before reporting.
Think step by step. Use the available tools to probe, enumerate, and confirm."""

SYSTEM_IDENTITY_COMPACT = """You are Aegix, an expert security testing agent with deep knowledge of OWASP Top 10, API Security Top 10, and Bugcrowd VRT. Be creative, thorough, and evidence-driven."""


def _identity_section(profile: str) -> str:
    return SYSTEM_IDENTITY_FULL if profile == "full" else SYSTEM_IDENTITY_COMPACT


def _objective_section() -> str:
    return (
        "## Objective\n\n"
        "1. Identify and confirm security vulnerabilities in the target application\n"
        "2. For each confirmed finding, provide clear evidence (request/response, output)\n"
        "3. Rate severity correctly (critical/high/medium/low/info)\n"
        "4. Suggest remediation steps\n"
        "5. Produce a structured penetration test report"
    )


def _target_section(target_info: dict, project_name: str, scan_mode: str, preset: str) -> str:
    lines = ["## Target Information\n"]
    if project_name:
        lines.append(f"- Project: {project_name}")
    if scan_mode:
        lines.append(f"- Scan mode: {scan_mode}")
    if preset:
        lines.append(f"- Preset: {preset}")
    for k, v in target_info.items():
        if isinstance(v, str) and v:
            lines.append(f"- {k}: {v}")
    return "\n".join(lines)


def _approach_section() -> str:
    return (
        "## Approach\n\n"
        "1. **Recon** - Enumerate the attack surface first\n"
        "2. **Load skills** - Use `load_skill` for relevant vulnerability classes\n"
        "3. **Probe** - Test endpoints with focused payloads using `http`\n"
        "4. **Verify** - Confirm findings with reproducible evidence\n"
        "5. **Report** - Use `confirm_finding` to record each vulnerability\n"
        "6. **Cover** - Track tested areas with `coverage` to avoid gaps"
    )


def _skills_section(registry: SkillRegistry) -> str:
    skills = registry.list_enabled()
    if not skills:
        return ""
    lines = ["## Available Skills\n"]
    for s in skills[:15]:
        lines.append(f"- **{s.name}**: {s.description}")
    lines.append("")
    lines.append("Use `load_skill(name=\"<skill>\")` before testing that vulnerability class.")
    return "\n".join(lines)


def _coverage_section(store: CoverageStore) -> str:
    try:
        summary = store.summary()
        entries = store.list()
    except Exception:
        return ""
    lines = ["## Coverage State\n"]
    lines.append(f"- Total entries: {summary.total}")
    if entries:
        lines.append("### Recent tests:")
        for e in entries[-5:]:
            lines.append(f"- {e.endpoint} | {e.param} | {e.vuln_class} | {e.status}")
    return "\n".join(lines)


def _intelligence_section(store: IntelligenceStore, target_info: dict) -> str:
    query = " ".join(str(v) for v in target_info.values() if isinstance(v, str))
    if not query:
        return ""
    results = store.search(query, limit=3)
    if not results:
        return ""
    lines = ["## Intelligence Context (from prior sessions)\n"]
    for r in results:
        s = r.scenario
        lines.append(f"- **{s.title}** (confidence: {s.confidence})")
        lines.append(f"  Lesson: {s.lesson[:200]}")
        if s.recommended_checks:
            lines.append(f"  Checks: {', '.join(s.recommended_checks[:4])}")
    return "\n".join(lines)


def _tool_usage_section() -> str:
    return (
        "## Tool Usage\n\n"
        "- `shell` - Execute commands (for local analysis, script execution)\n"
        "- `http` - Send HTTP requests to test endpoints\n"
        "- `web_fetch` - Fetch web pages to analyze content\n"
        "- `web_search` - Research CVEs, techniques, payloads\n"
        "- `file_read` - Read files from the project\n"
        "- `file_write` - Write output files\n"
        "- `glob` - Find files by pattern\n"
        "- `grep` - Search file contents\n"
        "- `load_skill` - Load a methodology playbook\n"
        "- `coverage` - Track what you have tested\n"
        "- `confirm_finding` - Record a confirmed vulnerability\n"
        "- `ask_user` - Ask me questions when you need input"
    )


def _report_format_section() -> str:
    return (
        "## Report Format\n\n"
        "When you have completed testing, produce a penetration test report with:\n"
        "- Executive summary\n"
        "- Attack chains (list of strings)\n"
        "- Reproduction plan (step by step)\n"
        "- Analysis limitations\n"
        "- Next steps / recommendations\n"
        "- Benchmark (findings_covered, paths_exercised, confidence_average, benchmark_summary)\n"
        "- Finding overrides with evidence for each confirmed vulnerability"
    )


def _no_thinking_section() -> str:
    return "Do not output thinking or reasoning blocks. Only output the final answer."
