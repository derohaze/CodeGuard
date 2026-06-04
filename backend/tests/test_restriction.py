"""Tests for tool restriction and sensitive path detection."""
from __future__ import annotations

import os

from app.infrastructure.ai.tools.restriction import (
    resolve_tool_name,
    is_tool_allowed,
    is_sensitive_path,
    TOOL_ALIASES,
)


class TestResolveToolName:
    def test_canonical_passthrough(self):
        assert resolve_tool_name("shell") == "shell"
        assert resolve_tool_name("http") == "http"
        assert resolve_tool_name("file_read") == "file_read"

    def test_alias_resolution(self):
        for alias, canonical in TOOL_ALIASES.items():
            assert resolve_tool_name(alias) == canonical, f"{alias} -> {canonical}"

    def test_unknown_passthrough(self):
        assert resolve_tool_name("alien_tech") == "alien_tech"


class TestIsToolAllowed:
    def test_no_skills_allows_all(self):
        assert is_tool_allowed("shell", None) is True
        assert is_tool_allowed("http", []) is True

    def test_allowed_tool(self):
        assert is_tool_allowed("http", [["http"]]) is True

    def test_blocked_tool(self):
        assert is_tool_allowed("shell", [["http"]]) is False

    def test_allowed_via_alias(self):
        assert is_tool_allowed("BashTool", [["shell"]]) is True

    def test_multiple_skills_union(self):
        assert is_tool_allowed("shell", [["http"], ["shell"]]) is True
        assert is_tool_allowed("glob", [["http"], ["shell"]]) is False

    def test_empty_skill_tools_allows(self):
        assert is_tool_allowed("shell", [[]]) is True


class TestIsSensitivePath:
    def test_dot_ssh(self):
        assert is_sensitive_path("~/.ssh/id_rsa") is True

    def test_dot_aws(self):
        assert is_sensitive_path("~/.aws/credentials") is True

    def test_etc_shadow(self):
        assert is_sensitive_path("/etc/shadow") is True

    def test_tmp_file_not_sensitive(self):
        assert is_sensitive_path("/tmp/test.txt") is False

    def test_home_expanded(self):
        expanded = os.path.join(os.path.expanduser("~"), ".ssh", "id_rsa")
        assert is_sensitive_path(expanded) is True

    def test_windows_backslash(self):
        home = os.path.expanduser("~")
        win_path = os.path.join(home, ".ssh", "config")
        assert is_sensitive_path(win_path) is True

    def test_docker_dir(self):
        assert is_sensitive_path("~/.docker/config.json") is True

    def test_normal_project_file(self):
        assert is_sensitive_path("/home/user/projects/app/main.py") is False
