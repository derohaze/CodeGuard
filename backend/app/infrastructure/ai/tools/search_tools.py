from __future__ import annotations

import fnmatch
import os
import re

from app.infrastructure.ai.tools.base import BaseTool, ToolResult

SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv"}
MAX_FILE_SIZE = 5 * 1024 * 1024


class GlobTool(BaseTool):
    name = "glob"
    description = "Find files matching a glob pattern. Skips node_modules, .git, dist, etc."
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern (e.g. '**/*.py', 'src/**/*.ts')",
            },
            "base_dir": {
                "type": "string",
                "description": "Base directory to search from (default: current directory)",
                "default": ".",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default 200, max 500)",
                "default": 200,
            },
        },
        "required": ["pattern"],
    }

    async def run(self, pattern: str, base_dir: str = ".", max_results: int = 200) -> ToolResult:
        base = os.path.abspath(os.path.expanduser(base_dir))
        if not os.path.isdir(base):
            return ToolResult.fail(f"directory not found: {base_dir}")
        max_results = max(1, min(max_results, 500))

        matches: list[str] = []
        try:
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                rel_root = os.path.relpath(root, base)
                for f in files:
                    rel_path = os.path.join(rel_root, f) if rel_root != "." else f
                    if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(os.path.basename(rel_path), pattern):
                        matches.append(rel_path)
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results:
                    break
        except Exception as exc:
            return ToolResult.fail(f"glob error: {exc}")

        if not matches:
            return ToolResult.ok("no matches found")
        return ToolResult.ok(f"found {len(matches)} file(s):\n" + "\n".join(matches))


class GrepTool(BaseTool):
    name = "grep"
    description = "Search file contents using a regex pattern. Max 5MB per file."
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regular expression to search for",
            },
            "include": {
                "type": "string",
                "description": "File glob pattern to include (e.g. '*.py', '*.{ts,js}')",
                "default": "*",
            },
            "base_dir": {
                "type": "string",
                "description": "Base directory to search (default: current directory)",
                "default": ".",
            },
            "max_matches": {
                "type": "integer",
                "description": "Maximum matches (default 100, max 500)",
                "default": 100,
            },
        },
        "required": ["pattern"],
    }

    async def run(self, pattern: str, include: str = "*", base_dir: str = ".", max_matches: int = 100) -> ToolResult:
        base = os.path.abspath(os.path.expanduser(base_dir))
        if not os.path.isdir(base):
            return ToolResult.fail(f"directory not found: {base_dir}")
        max_matches = max(1, min(max_matches, 500))

        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            return ToolResult.fail(f"invalid regex: {exc}")

        matches: list[str] = []
        try:
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for f in files:
                    if not fnmatch.fnmatch(f, include):
                        continue
                    file_path = os.path.join(root, f)
                    try:
                        size = os.path.getsize(file_path)
                        if size > MAX_FILE_SIZE:
                            continue
                        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                            for line_no, line in enumerate(fh, 1):
                                if compiled.search(line):
                                    rel = os.path.relpath(file_path, base)
                                    matches.append(f"{rel}:{line_no}: {line.rstrip()[:200]}")
                                    if len(matches) >= max_matches:
                                        break
                        if len(matches) >= max_matches:
                            break
                    except (OSError, UnicodeDecodeError):
                        continue
                if len(matches) >= max_matches:
                    break
        except Exception as exc:
            return ToolResult.fail(f"grep error: {exc}")

        if not matches:
            return ToolResult.ok("no matches found")
        return ToolResult.ok(f"found {len(matches)} match(es):\n" + "\n".join(matches))
