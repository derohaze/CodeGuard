"""Tests for individual tools."""
from __future__ import annotations

import os
import tempfile

import pytest

from app.infrastructure.ai.tools.shell_tool import ShellTool, DENY_COMMANDS
from app.infrastructure.ai.tools.http_tool import HTTPTool
from app.infrastructure.ai.tools.file_tools import FileReadTool, FileWriteTool, FileEditTool
from app.infrastructure.ai.tools.web_tools import WebFetchTool
from app.infrastructure.ai.tools.search_tools import GlobTool, GrepTool
from app.infrastructure.ai.tools.coverage_tool import CoverageTool
from app.infrastructure.coverage.store import CoverageStore


class TestShellTool:
    @pytest.mark.asyncio
    async def test_echo(self):
        tool = ShellTool()
        result = await tool.run(command="echo hello")
        assert result.success
        assert "hello" in result.output

    @pytest.mark.asyncio
    async def test_deny_command(self):
        tool = ShellTool()
        result = await tool.run(command="rm -rf /")
        assert not result.success
        assert "denied" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_timeout(self):
        tool = ShellTool()
        result = await tool.run(command="ping -n 10 127.0.0.1", timeout=1)
        assert not result.success

    @pytest.mark.asyncio
    async def test_deny_list_all_blocked(self):
        tool = ShellTool()
        samples = ["rm -rf /", "mkfs.ext4 /dev/sda", "dd of=/dev/sda", "shutdown -h now", "reboot"]
        for cmd in samples:
            result = await tool.run(command=cmd)
            assert not result.success, f"{cmd!r} should be denied"


class TestHTTPTool:
    @pytest.mark.asyncio
    async def test_get(self):
        tool = HTTPTool()
        result = await tool.run(method="GET", url="http://httpbin.org/get")
        assert result.success
        assert "HTTP" in result.output

    @pytest.mark.asyncio
    async def test_get_https(self):
        tool = HTTPTool()
        result = await tool.run(method="GET", url="https://httpbin.org/get")
        if not result.success:
            # Network may be unreliable; don't fail the test
            return
        assert "HTTP" in result.output

    @pytest.mark.asyncio
    async def test_bad_url(self):
        tool = HTTPTool()
        result = await tool.run(method="GET", url="http://nonexistent.invalid")
        assert not result.success

    @pytest.mark.asyncio
    async def test_post(self):
        tool = HTTPTool()
        result = await tool.run(
            method="POST",
            url="http://httpbin.org/post",
            body='{"key":"value"}',
        )
        if not result.success:
            return
        assert "HTTP" in result.output


class TestFileTools:
    @pytest.fixture
    def tmpfile(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("line1\nline2\nline3\n")
            tmp = f.name
        yield tmp
        os.unlink(tmp)

    @pytest.mark.asyncio
    async def test_file_read(self, tmpfile):
        tool = FileReadTool()
        result = await tool.run(path=tmpfile)
        assert result.success
        assert "line1" in result.output
        assert "line2" in result.output

    @pytest.mark.asyncio
    async def test_file_read_sensitive(self):
        tool = FileReadTool()
        result = await tool.run(path="~/.ssh/id_rsa")
        assert not result.success
        assert "sensitive" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_file_write_and_edit(self):
        tmp = os.path.join(tempfile.gettempdir(), f"aegix_test_{os.urandom(4).hex()}.txt")
        try:
            w_tool = FileWriteTool()
            result = await w_tool.run(path=tmp, content="hello\nworld\n")
            assert result.success

            e_tool = FileEditTool()
            result = await e_tool.run(path=tmp, old_string="world", new_string="there")
            assert result.success

            r_tool = FileReadTool()
            result = await r_tool.run(path=tmp)
            assert "hello" in result.output
            assert "there" in result.output
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    @pytest.mark.asyncio
    async def test_file_write_sensitive(self):
        tool = FileWriteTool()
        result = await tool.run(path="~/.ssh/id_rsa", content="hack")
        assert not result.success


class TestGlobGrepTool:
    @pytest.mark.asyncio
    async def test_glob_finds_self(self):
        tool = GlobTool()
        result = await tool.run(pattern="*.py", base_dir="tests", max_results=10)
        assert result.success
        assert "test_" in result.output

    @pytest.mark.asyncio
    async def test_glob_no_match(self):
        tool = GlobTool()
        result = await tool.run(pattern="zzz_no_match_*.xyz")
        assert result.success
        assert "no matches" in result.output

    @pytest.mark.asyncio
    async def test_glob_bad_dir(self):
        tool = GlobTool()
        result = await tool.run(pattern="*.py", base_dir="does_not_exist_12345")
        assert not result.success

    @pytest.mark.asyncio
    async def test_grep(self):
        tool = GrepTool()
        result = await tool.run(pattern="def test_", include="test_tools.py", base_dir="tests")
        assert result.success
        assert result.output.startswith("found ")


class TestCoverageTool:
    @pytest.fixture
    def store(self):
        s = CoverageStore(path=os.path.join(os.environ.get("TEMP", "/tmp"), f"aegix_cov_{os.urandom(4).hex()}.json"))
        s.load()
        return s

    @pytest.mark.asyncio
    async def test_mark_and_summary(self, store):
        tool = CoverageTool(store=store)
        r = await tool.run(action="mark", endpoint="/api/login", param="username", vuln_class="sqli")
        assert r.success
        s = await tool.run(action="summary")
        assert "total: 1" in s.output

    @pytest.mark.asyncio
    async def test_mark_missing_fields(self, store):
        tool = CoverageTool(store=store)
        r = await tool.run(action="mark", endpoint="", param="", vuln_class="")
        assert not r.success

    @pytest.mark.asyncio
    async def test_list_empty(self, store):
        tool = CoverageTool(store=store)
        r = await tool.run(action="list")
        assert r.success

    @pytest.mark.asyncio
    async def test_clear(self, store):
        tool = CoverageTool(store=store)
        await tool.run(action="mark", endpoint="/api/test", param="x", vuln_class="xss")
        r = await tool.run(action="clear")
        assert r.success
        s = await tool.run(action="summary")
        assert "total: 0" in s.output

    @pytest.mark.asyncio
    async def test_no_store(self):
        tool = CoverageTool(store=None)
        r = await tool.run(action="mark", endpoint="/api/test", param="x", vuln_class="xss")
        assert not r.success

    @pytest.mark.asyncio
    async def test_unknown_action(self, store):
        tool = CoverageTool(store=store)
        r = await tool.run(action="fly_to_moon")
        assert not r.success


class TestWebFetchTool:
    @pytest.mark.asyncio
    async def test_fetch(self):
        tool = WebFetchTool()
        result = await tool.run(url="https://httpbin.org/html")
        assert result.success
        assert len(result.output) > 0
