import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.entities.scan import FindingEntity
from app.infrastructure.services.scan.score_calibration import calibrate_security_score


def make_finding(severity: str, confidence: int = 90) -> FindingEntity:
    return FindingEntity(
        id=f"{severity}-1",
        severity=severity,  # type: ignore[arg-type]
        title=f"{severity} finding",
        file="demo.py",
        line=10,
        line_end=12,
        category="Security review",
        confidence=confidence,
        summary="summary",
        impact="impact",
        attack_input="input",
        attack_execution="execution",
        attack_result="result",
        audit_log=["log"],
        explanation="explanation",
        fix_suggestions=[],
        evidence="snippet",
    )


class ScoreCalibrationTests(unittest.TestCase):
    def test_full_coverage_with_path_evidence_on_supported_stack_can_score_perfect(self) -> None:
        result = calibrate_security_score(
            validated_findings=[],
            candidate_findings=[],
            coverage_snapshot={"coverage_percent": 100},
            framework_profile={"primary_framework": "express", "frameworks": ["express"]},
            path_summary={"candidate_path_count": 4},
        )
        self.assertEqual(result["score"], 100)

    def test_full_coverage_without_paths_is_not_perfect(self) -> None:
        result = calibrate_security_score(
            validated_findings=[],
            candidate_findings=[],
            coverage_snapshot={"coverage_percent": 100},
            framework_profile={"primary_framework": "spring", "frameworks": ["spring"]},
            path_summary={"candidate_path_count": 0},
        )
        self.assertLess(result["score"], 100)
        self.assertEqual(result["rationale"]["path_count"], 0)

    def test_full_coverage_without_paths_on_fastapi_is_cautious_but_not_harsh(self) -> None:
        result = calibrate_security_score(
            validated_findings=[],
            candidate_findings=[],
            coverage_snapshot={"coverage_percent": 100},
            framework_profile={"primary_framework": "fastapi", "frameworks": ["fastapi"]},
            path_summary={"candidate_path_count": 0},
        )
        self.assertGreaterEqual(result["score"], 90)
        self.assertLess(result["score"], 100)

    def test_candidate_pressure_lowers_partial_safe_score(self) -> None:
        result = calibrate_security_score(
            validated_findings=[],
            candidate_findings=[make_finding("high", 60)],
            coverage_snapshot={"coverage_percent": 80},
            framework_profile={"primary_framework": "express", "frameworks": ["express"]},
            path_summary={"candidate_path_count": 2},
        )
        self.assertLess(result["score"], 99)
        self.assertGreaterEqual(result["rationale"]["candidate_pressure"], 1)

    def test_validated_findings_drive_score_down(self) -> None:
        result = calibrate_security_score(
            validated_findings=[make_finding("critical", 95), make_finding("high", 90)],
            candidate_findings=[],
            coverage_snapshot={"coverage_percent": 100},
            framework_profile={"primary_framework": "express", "frameworks": ["express"]},
            path_summary={"candidate_path_count": 3},
        )
        self.assertLess(result["score"], 70)


if __name__ == "__main__":
    unittest.main()
