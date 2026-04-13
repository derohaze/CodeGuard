from __future__ import annotations

from typing import Any

from app.infrastructure.learning.fingerprints import bounded_identifier, stable_fingerprint
from app.infrastructure.learning.schemas import NormalizedBenchmarkCase


def build_default_detection_ground_truth_cases() -> list[dict[str, Any]]:
    seeds = [
        {
            "title": "SQL Injection in dynamic query",
            "weakness_id": "CWE-89",
            "vulnerability_category": "sql_injection",
            "language": "java",
            "severity": "high",
        },
        {
            "title": "Cross-site Scripting via unsanitized output",
            "weakness_id": "CWE-79",
            "vulnerability_category": "xss",
            "language": "java",
            "severity": "high",
        },
        {
            "title": "OS Command Injection from untrusted input",
            "weakness_id": "CWE-78",
            "vulnerability_category": "command_injection",
            "language": "c",
            "severity": "high",
        },
        {
            "title": "Path Traversal on file include/read",
            "weakness_id": "CWE-22",
            "vulnerability_category": "path_traversal",
            "language": "c",
            "severity": "high",
        },
        {
            "title": "SSRF through unchecked remote URL fetch",
            "weakness_id": "CWE-918",
            "vulnerability_category": "ssrf",
            "language": "java",
            "severity": "high",
        },
        {
            "title": "Insecure deserialization of attacker-controlled object",
            "weakness_id": "CWE-502",
            "vulnerability_category": "insecure_deserialization",
            "language": "java",
            "severity": "high",
        },
    ]

    cases: list[dict[str, Any]] = []
    for seed in seeds:
        payload = {
            "suite_name": "detection",
            "title": seed["title"],
            "weakness_id": seed["weakness_id"],
            "vulnerability_category": seed["vulnerability_category"],
            "language": seed["language"],
            "severity": seed["severity"],
            "ground_truth": "juliet",
        }
        case = NormalizedBenchmarkCase(
            case_id=bounded_identifier("bench_case", payload),
            suite_name="detection",
            source_system="juliet_test_suite_seed",
            vulnerability_category=seed["vulnerability_category"],
            language=seed["language"],
            framework=None,
            severity=seed["severity"],
            expected_status="validated",
            ground_truth_confidence=95,
            provenance={
                "dataset": "juliet_test_suite",
                "weakness_id": seed["weakness_id"],
                "seed_version": "2026.04",
            },
            payload={"title": seed["title"], "weakness_id": seed["weakness_id"]},
            content_fingerprint=stable_fingerprint(payload),
        )
        cases.append(case.model_dump())
    return cases
