from __future__ import annotations

import os
import re


SENSITIVE_PATH_PATTERNS: list[re.Pattern] = [
    re.compile(r"(~|%USERPROFILE%|\$HOME)[/\\]\.ssh"),
    re.compile(r"(~|%USERPROFILE%|\$HOME)[/\\]\.aws"),
    re.compile(r"(~|%USERPROFILE%|\$HOME)[/\\]\.gnupg"),
    re.compile(r"(~|%USERPROFILE%|\$HOME)[/\\]\.gcloud"),
    re.compile(r"(~|%USERPROFILE%|\$HOME)[/\\]\.kube"),
    re.compile(r"(~|%USERPROFILE%|\$HOME)[/\\]\.docker"),
    re.compile(r"(~|%USERPROFILE%|\$HOME)[/\\]\.config[/\\]gcloud"),
    re.compile(r"(~|%USERPROFILE%|\$HOME)[/\\]\.config[/\\]op"),
    re.compile(r"(~|%USERPROFILE%|\$HOME)[/\\]\.netrc"),
    re.compile(r"(~|%USERPROFILE%|\$HOME)[/\\]\.pgpass"),
    re.compile(r"(~|%USERPROFILE%|\$HOME)[/\\]\.npmrc"),
    re.compile(r"(~|%USERPROFILE%|\$HOME)[/\\]\.pypirc"),
    re.compile(r"/etc/shadow"),
    re.compile(r"/etc/sudoers"),
    re.compile(r"/etc/passwd"),
    re.compile(r"/etc/kubernetes"),
]

TOOL_ALIASES: dict[str, str] = {
    "bash": "shell",
    "sh": "shell",
    "shell_tool": "shell",
    "BashTool": "shell",
    "ShellTool": "shell",
    "file_read": "file_read",
    "FileReadTool": "file_read",
    "file_write": "file_write",
    "FileWriteTool": "file_write",
    "file_edit": "file_edit",
    "FileEditTool": "file_edit",
    "http": "http",
    "HTTPTool": "http",
    "web_fetch": "web_fetch",
    "WebFetchTool": "web_fetch",
    "web_search": "web_search",
    "WebSearchTool": "web_search",
    "glob": "glob",
    "GlobTool": "glob",
    "grep": "grep",
    "GrepTool": "grep",
    "coverage": "coverage",
    "CoverageTool": "coverage",
    "ask_user": "ask_user",
    "AskUserTool": "ask_user",
    "confirm_finding": "confirm_finding",
    "ConfirmFindingTool": "confirm_finding",
    "load_skill": "load_skill",
    "LoadSkillTool": "load_skill",
}


def resolve_tool_name(name: str) -> str:
    return TOOL_ALIASES.get(name, name)


def is_tool_allowed(
    tool_name: str,
    active_skill_tools: list[list[str]] | None = None,
) -> bool:
    canonical = resolve_tool_name(tool_name)
    if not active_skill_tools:
        return True
    skill_allowed: set[str] = set()
    for allowed_list in active_skill_tools:
        skill_allowed.update(resolve_tool_name(a) for a in allowed_list)
    if not skill_allowed:
        return True
    return canonical in skill_allowed


def is_sensitive_path(path: str) -> bool:
    check_paths = [path.replace("/", "\\"), path.replace("\\", "/")]
    expanded = os.path.expanduser(path)
    expanded = os.path.abspath(expanded)
    check_paths.append(expanded)
    check_paths.append(expanded.replace("\\", "/"))
    home = os.path.expanduser("~")
    for p in check_paths:
        for pattern in SENSITIVE_PATH_PATTERNS:
            if pattern.search(p):
                return True
        for sensitive_dir in [".ssh", ".aws", ".gnupg", ".kube", ".docker", ".config"]:
            sensitive_path = os.path.join(home, sensitive_dir)
            if p.startswith(sensitive_path):
                return True
    return False
