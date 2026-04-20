from __future__ import annotations

from typing import TypedDict


class PenetrationBenchmark(TypedDict):
    findings_covered: int
    paths_exercised: int
    confidence_average: int
    benchmark_summary: str


class FindingOverride(TypedDict):
    file: str
    line: int
    title: str
    attack_input: str
    attack_execution: str
    attack_result: str
    explanation: str
    audit_log: list[str]


class PenetrationReport(TypedDict):
    review_note: str
    executive_summary: str
    attack_chains: list[str]
    reproduction_plan: list[str]
    analysis_limitations: list[str]
    next_steps: list[str]
    benchmark: PenetrationBenchmark
    finding_overrides: list[FindingOverride]
