from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel


class IntelligenceScenario(BaseModel):
    id: str
    title: str
    category: str
    triggers: list[str] = []
    technologies: list[str] = []
    lesson: str = ""
    recommended_checks: list[str] = []
    avoid_missing: list[str] = []
    source: str = ""
    source_session_id: Optional[str] = None
    created_at: str = ""
    updated_at: Optional[str] = None
    confidence: float = 0.7
    scope: str = "project"


class SearchResult(BaseModel):
    scenario: IntelligenceScenario
    score: float = 0.0
    matched: list[str] = []
