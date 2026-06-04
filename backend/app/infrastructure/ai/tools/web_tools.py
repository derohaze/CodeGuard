from __future__ import annotations

import asyncio
import re
from typing import Any

from app.infrastructure.ai.tools.base import BaseTool, ToolResult

MAX_TEXT_CHARS = 40960
FETCH_TIMEOUT = 30


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "Fetch a web page and return its text content (HTML stripped)."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch",
            },
            "timeout": {
                "type": "integer",
                "description": f"Timeout in seconds (default {FETCH_TIMEOUT})",
                "default": FETCH_TIMEOUT,
            },
        },
        "required": ["url"],
    }

    async def run(self, url: str, timeout: int = FETCH_TIMEOUT) -> ToolResult:
        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; Aegix/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
        except urllib.error.URLError as exc:
            return ToolResult.fail(f"connection error: {exc.reason}")
        except Exception as exc:
            return ToolResult.fail(f"fetch failed: {exc}")

        html = raw.decode("utf-8", errors="replace")
        text = re.sub(r"<head[^>]*>.*?</head>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        lines = re.split(r"[.\n]", text)
        text = "\n".join(l.strip() for l in lines if l.strip())

        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS] + f"\n... (truncated at {MAX_TEXT_CHARS} chars)"
        return ToolResult.ok(text)


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for current information. Returns text summaries of top results."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results (default 5, max 10)",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def run(self, query: str, max_results: int = 5) -> ToolResult:
        max_results = max(1, min(max_results, 10))
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return ToolResult.fail(
                "web_search requires duckduckgo_search. Install with: pip install duckduckgo_search"
            )

        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, lambda: list(DDGS().text(query, max_results=max_results))
            )
        except Exception as exc:
            return ToolResult.fail(f"search failed: {exc}")

        if not results:
            return ToolResult.ok("no results found")

        lines: list[str] = []
        for i, r in enumerate(results[:max_results], 1):
            title = r.get("title", "")
            snippet = r.get("body", r.get("snippet", ""))
            href = r.get("href", "")
            lines.append(f"{i}. {title}")
            if href:
                lines.append(f"   URL: {href}")
            if snippet:
                lines.append(f"   {snippet}")
            lines.append("")

        return ToolResult.ok("\n".join(lines))
