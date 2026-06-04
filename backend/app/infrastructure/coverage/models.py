from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


CoverageStatus = Literal["tried", "passed", "failed", "waf-blocked", "skipped"]


class CoverageEntry(BaseModel):
    endpoint: str
    param: str
    vuln_class: str
    status: str = "tried"
    count: int = 1
    first_seen: float = 0.0
    last_seen: float = 0.0
    notes: Optional[str] = None


class CoverageSummary(BaseModel):
    total: int = 0
    by_status: dict[str, int] = {}
    by_vuln_class: dict[str, int] = {}
