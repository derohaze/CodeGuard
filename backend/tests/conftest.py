from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("APP_NAME", "Aegix-Test")
os.environ.setdefault("ARTIFACTS_DIR", os.path.join(os.environ.get("TEMP", "/tmp"), "aegix_test_artifacts"))


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM that returns a final (non-tool-call) response by default."""
    mock = AsyncMock()
    mock.return_value = {"role": "assistant", "content": "done", "type": "final"}
    return mock


@pytest.fixture
def tool_registry():
    """Build a real ToolRegistry with all 12 tools loaded."""
    from app.infrastructure.ai.tools import (
        ToolRegistry,
        ShellTool, HTTPTool,
        FileReadTool, FileWriteTool, FileEditTool,
        WebFetchTool, WebSearchTool,
        GlobTool, GrepTool,
        CoverageTool, AskUserTool, ConfirmFindingTool,
    )
    from app.infrastructure.coverage.store import CoverageStore

    reg = ToolRegistry()
    cover = CoverageStore(path=os.path.join(os.environ["ARTIFACTS_DIR"], "test_coverage.json"))
    cover.load()
    reg.register_many(
        ShellTool(),
        HTTPTool(),
        FileReadTool(),
        FileWriteTool(),
        FileEditTool(),
        WebFetchTool(),
        WebSearchTool(),
        GlobTool(),
        GrepTool(),
        CoverageTool(store=cover),
        AskUserTool(),
        ConfirmFindingTool(),
    )
    return reg


@pytest.fixture
def agent_loop_factory():
    from app.infrastructure.ai.tools.agent_loop import InteractiveAgentLoop

    def make(mock_fn=None):
        return InteractiveAgentLoop(tool_registry=None if mock_fn else None, llm_chat_fn=mock_fn or AsyncMock())
    return make
