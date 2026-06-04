from __future__ import annotations

import asyncio
from typing import Any

from app.infrastructure.ai.tools.base import BaseTool, ToolResult

MAX_RESPONSE_CHARS = 262144
DEFAULT_TIMEOUT = 60


class HTTPTool(BaseTool):
    name = "http"
    description = "Send an HTTP request to a target URL. Use for testing endpoints, APIs, and web targets."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                "description": "HTTP method",
                "default": "GET",
            },
            "url": {
                "type": "string",
                "description": "Full URL to request",
            },
            "headers": {
                "type": "object",
                "description": "Additional headers as key-value pairs",
                "default": {},
            },
            "body": {
                "type": "string",
                "description": "Request body (for POST/PUT/PATCH)",
                "default": "",
            },
            "timeout": {
                "type": "integer",
                "description": f"Request timeout in seconds (default {DEFAULT_TIMEOUT})",
                "default": DEFAULT_TIMEOUT,
            },
        },
        "required": ["url"],
    }
    requires_permission = True

    async def run(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str = "",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> ToolResult:
        import urllib.parse

        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return ToolResult.fail(f"invalid URL: {url}")

        if headers is None:
            headers = {}

        try:
            import aiohttp
        except ImportError:
            return await self._run_stdlib(url, method, headers, body, timeout)

        return await self._run_aiohttp(url, method, headers, body, timeout)

    async def _run_stdlib(self, url: str, method: str, headers: dict[str, str] | None, body: str, timeout: int) -> ToolResult:
        import urllib.request
        import urllib.error

        try:
            req = urllib.request.Request(
                url,
                data=body.encode() if body else None,
                headers=headers or {},
                method=method,
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
        except urllib.error.URLError as exc:
            return ToolResult.fail(f"connection error: {exc.reason}")
        except Exception as exc:
            return ToolResult.fail(f"request failed: {exc}")
        else:
            status = resp.status

        response_text = raw.decode("utf-8", errors="replace")
        if len(response_text) > MAX_RESPONSE_CHARS:
            response_text = response_text[:MAX_RESPONSE_CHARS] + f"\n... (truncated at {MAX_RESPONSE_CHARS} chars)"
        return ToolResult.ok(f"HTTP {status}\n\n{response_text}")

    async def _run_aiohttp(self, url: str, method: str, headers: dict[str, str] | None, body: str, timeout: int) -> ToolResult:
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=body if body else None,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    ssl=False,
                ) as resp:
                    raw = await resp.read()
                    status = resp.status
        except asyncio.TimeoutError:
            return ToolResult.fail(f"request timed out after {timeout}s")
        except aiohttp.ClientError as exc:
            return ToolResult.fail(f"http error: {exc}")
        except Exception as exc:
            return ToolResult.fail(f"request failed: {exc}")

        response_text = raw.decode("utf-8", errors="replace")
        if len(response_text) > MAX_RESPONSE_CHARS:
            response_text = response_text[:MAX_RESPONSE_CHARS] + f"\n... (truncated at {MAX_RESPONSE_CHARS} chars)"
        return ToolResult.ok(f"HTTP {status}\n\n{response_text}")
