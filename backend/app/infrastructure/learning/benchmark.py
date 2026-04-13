from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from app.infrastructure.learning.benchmark_seed_data import build_default_detection_ground_truth_cases
from app.infrastructure.learning.repository import LearningArchiveMongoRepository


BENCHMARK_SUITES = (
    "detection",
    "remediation",
    "verification",
    "ingestion_normalization",
)


@dataclass(slots=True)
class BenchmarkRunSummary:
    run_id: str
    suite_name: str
    status: str
    metrics: dict
    artifacts: dict


class LearningBenchmarkService:
    def __init__(self, repository: LearningArchiveMongoRepository) -> None:
        self.repository = repository

    async def ensure_benchmark_skeleton(self) -> None:
        for suite_name in BENCHMARK_SUITES:
            await self.repository.upsert_benchmark_suite(
                suite_name,
                metadata={
                    "schema_version": "1.0.0",
                    "description": f"{suite_name} benchmark suite",
                    "ground_truth": "human_approved_findings_plus_juliet",
                },
            )
        await self._ensure_detection_ground_truth_cases()

    async def _ensure_detection_ground_truth_cases(self) -> None:
        for case in build_default_detection_ground_truth_cases():
            await self.repository.upsert_benchmark_case(case)

    async def run_suite(self, suite_name: str) -> BenchmarkRunSummary:
        if suite_name not in BENCHMARK_SUITES:
            raise ValueError(f"Unsupported benchmark suite '{suite_name}'.")

        await self.ensure_benchmark_skeleton()
        run_id = await self.repository.create_benchmark_run(
            suite_name=suite_name,
            benchmark_type=suite_name,
            metadata={"runner": "learning_benchmark_service_v1"},
        )
        metrics, artifacts = await self._evaluate_suite(suite_name)
        status = "passed" if bool(metrics.get("passed")) else "failed"
        await self.repository.finalize_benchmark_run(
            run_id,
            status=status,
            metrics=metrics,
            artifacts=artifacts,
        )
        return BenchmarkRunSummary(
            run_id=run_id,
            suite_name=suite_name,
            status=status,
            metrics=metrics,
            artifacts=artifacts,
        )

    async def run_all(self) -> list[BenchmarkRunSummary]:
        summaries: list[BenchmarkRunSummary] = []
        for suite in BENCHMARK_SUITES:
            summaries.append(await self.run_suite(suite))
        return summaries

    async def _evaluate_suite(self, suite_name: str) -> tuple[dict, dict]:
        if suite_name == "detection":
            return await self._evaluate_detection()
        if suite_name == "remediation":
            return await self._evaluate_remediation()
        if suite_name == "verification":
            return await self._evaluate_verification()
        return await self._evaluate_ingestion_normalization()

    async def _evaluate_detection(self) -> tuple[dict, dict]:
        items = await self.repository.list_archive_items(
            statuses=["suspected", "candidate", "validated", "rejected", "false_positive"],
            limit=1000,
        )
        juliet_cases = await self.repository.list_benchmark_cases(suite_name="detection", limit=1000)
        findings = [item for item in items if item.get("record_type") == "finding"]
        total = len(findings)
        if total == 0:
            return {"passed": False, "reason": "no_detection_items"}, {"sample_size": 0}

        validated = [item for item in findings if item.get("status") == "validated"]
        false_positive = [item for item in findings if item.get("status") in {"false_positive", "rejected"}]
        evidence_present = [item for item in findings if int(item.get("body_chunk_count", 0)) > 0]
        category_present = [item for item in findings if item.get("vulnerability_category")]
        severity_present = [item for item in findings if item.get("severity")]

        detection_rate = len(validated) / total
        false_positive_rate = len(false_positive) / total
        evidence_presence_rate = len(evidence_present) / total
        category_accuracy_proxy = len(category_present) / total
        severity_alignment_proxy = len(severity_present) / total
        juliet_categories = {
            str(case.get("vulnerability_category")).strip().lower()
            for case in juliet_cases
            if case.get("vulnerability_category")
        }
        predicted_categories = {
            str(item.get("vulnerability_category")).strip().lower()
            for item in findings
            if item.get("vulnerability_category")
        }
        juliet_category_coverage = (
            len(juliet_categories & predicted_categories) / len(juliet_categories)
            if juliet_categories
            else 1.0
        )
        passed = (
            detection_rate >= 0.45
            and false_positive_rate <= 0.35
            and evidence_presence_rate >= 0.75
            and juliet_category_coverage >= 0.5
        )
        metrics = {
            "passed": passed,
            "sample_size": total,
            "detection_rate": round(detection_rate, 4),
            "false_positive_rate": round(false_positive_rate, 4),
            "evidence_presence_rate": round(evidence_presence_rate, 4),
            "category_accuracy_proxy": round(category_accuracy_proxy, 4),
            "severity_alignment_proxy": round(severity_alignment_proxy, 4),
            "juliet_category_coverage": round(juliet_category_coverage, 4),
            "juliet_case_count": len(juliet_cases),
        }
        artifacts = {
            "suite": "detection",
            "ground_truth": "human_approved_findings_plus_juliet",
            "ground_truth_sources": ["learning_archive_items", "benchmark_cases:detection"],
        }
        return metrics, artifacts

    async def _evaluate_remediation(self) -> tuple[dict, dict]:
        items = await self.repository.list_archive_items(
            statuses=["patch_generated", "patch_approved", "patch_rejected", "applied", "verified_fixed", "verified_partial", "validation_failed", "rolled_back"],
            limit=1000,
        )
        patch_items = [item for item in items if item.get("record_type") == "patch"]
        total = len(patch_items)
        if total == 0:
            return {"passed": False, "reason": "no_patch_items"}, {"sample_size": 0}

        verified_fixed = [item for item in patch_items if item.get("status") == "verified_fixed"]
        applied = [item for item in patch_items if item.get("status") in {"applied", "verified_fixed", "verified_partial"}]
        regressions = [item for item in patch_items if item.get("status") in {"validation_failed", "rolled_back"}]
        minimality_samples = [len((item.get("payload") or {}).get("file_paths") or []) for item in patch_items]
        minimality_score = 1.0 - min(1.0, (mean(minimality_samples) - 1) / 5) if minimality_samples else 0.0
        correctness = len(verified_fixed) / total
        completeness = len(applied) / total
        regression_risk = len(regressions) / total
        passed = correctness >= 0.35 and completeness >= 0.6 and regression_risk <= 0.4
        metrics = {
            "passed": passed,
            "sample_size": total,
            "patch_correctness_rate": round(correctness, 4),
            "patch_completeness_rate": round(completeness, 4),
            "regression_risk_rate": round(regression_risk, 4),
            "patch_minimality_score": round(max(0.0, minimality_score), 4),
        }
        return metrics, {"suite": "remediation"}

    async def _evaluate_verification(self) -> tuple[dict, dict]:
        items = await self.repository.list_archive_items(
            statuses=["applied", "verified_fixed", "verified_partial", "validation_failed", "rolled_back"],
            limit=1000,
        )
        verification_items = [item for item in items if item.get("record_type") in {"verification", "patch"}]
        total = len(verification_items)
        if total == 0:
            return {"passed": False, "reason": "no_verification_items"}, {"sample_size": 0}

        fixed = [item for item in verification_items if item.get("status") == "verified_fixed"]
        partial = [item for item in verification_items if item.get("status") == "verified_partial"]
        failed = [item for item in verification_items if item.get("status") in {"validation_failed", "rolled_back"}]
        consistency_rate = (len(fixed) + len(partial)) / total
        failure_rate = len(failed) / total
        passed = consistency_rate >= 0.55 and failure_rate <= 0.45
        metrics = {
            "passed": passed,
            "sample_size": total,
            "verification_consistency_rate": round(consistency_rate, 4),
            "verification_failure_rate": round(failure_rate, 4),
        }
        return metrics, {"suite": "verification"}

    async def _evaluate_ingestion_normalization(self) -> tuple[dict, dict]:
        audits = await self.repository.list_recent_ingestion_audits(limit=500)
        total_audits = len(audits)
        failures = await self.repository.count_normalization_failures()
        successful = [item for item in audits if item.get("status") == "completed"]
        if total_audits == 0:
            return {"passed": False, "reason": "no_ingestion_audits"}, {"sample_size": 0}

        parser_correctness_proxy = len(successful) / total_audits
        normalization_failure_rate = failures / max(1, total_audits)
        idempotency_proxy = len([item for item in audits if (item.get("details") or {}).get("skipped_items", 0) > 0]) / total_audits
        passed = parser_correctness_proxy >= 0.7 and normalization_failure_rate <= 0.3
        metrics = {
            "passed": passed,
            "sample_size": total_audits,
            "parser_correctness_proxy": round(parser_correctness_proxy, 4),
            "normalization_failure_rate": round(normalization_failure_rate, 4),
            "idempotency_proxy": round(idempotency_proxy, 4),
        }
        return metrics, {"suite": "ingestion_normalization"}
