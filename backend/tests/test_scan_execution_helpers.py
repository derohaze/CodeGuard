from pathlib import Path
import sys
import tempfile
import unittest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.services.scan.scan_execution_service import (
    build_penetration_fallback_report,
    build_repository_map_fallback,
    build_candidate_review_findings,
    build_penetration_log_lines,
    enrich_findings_with_penetration_overrides,
    merge_runtime_metrics_with_agent_pipeline,
    merge_analysis_brief_with_penetration,
    merge_runtime_metrics_with_penetration_sandbox,
)


class ScanExecutionHelperTests(unittest.TestCase):
    def test_candidate_review_omits_items_promoted_to_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sample = root / "router.py"
            sample.write_text("query = request.args.get('q')\nrun(query)\n", encoding="utf-8")

            validated_findings = [
                {
                    "file": "router.py",
                    "line": 1,
                    "line_end": 2,
                    "title": "Dynamic query construction may allow injection",
                    "category": "SQL injection",
                    "path_hint": "request.args -> run(query)",
                    "source_hint": "router.py:1",
                    "sink_hint": "router.py:2",
                }
            ]
            candidate_findings = [
                {
                    "file": "router.py",
                    "line": 2,
                    "line_end": 2,
                    "title": "Dynamic query construction may allow injection",
                    "category": "SQL injection",
                    "path_hint": "request.args -> run(query)",
                    "source_hint": "router.py:1",
                    "sink_hint": "router.py:2",
                    "confidence": 79,
                }
            ]

            review_items = build_candidate_review_findings(
                candidate_findings=candidate_findings,
                validated_findings=validated_findings,
                source_root=root,
                files=[sample],
            )

            self.assertEqual(review_items, [])

    def test_penetration_overrides_update_attack_fields_for_matching_finding(self) -> None:
        findings = [
            {
                "file": "router.py",
                "line": 12,
                "title": "Unsanitized SQL execution",
                "attack_input": "old-input",
                "attack_execution": "old-execution",
                "attack_result": "old-result",
                "explanation": "old-explanation",
                "audit_log": ["existing"],
            }
        ]
        report = {
            "finding_overrides": [
                {
                    "file": "router.py",
                    "line": 12,
                    "title": "Unsanitized SQL execution",
                    "attack_input": "new-input",
                    "attack_execution": "new-execution",
                    "attack_result": "new-result",
                    "explanation": "new-explanation",
                    "audit_log": ["path replay confirmed"],
                }
            ]
        }

        enriched = enrich_findings_with_penetration_overrides(findings, report)

        self.assertEqual(enriched[0]["attack_input"], "new-input")
        self.assertEqual(enriched[0]["attack_execution"], "new-execution")
        self.assertEqual(enriched[0]["attack_result"], "new-result")
        self.assertEqual(enriched[0]["explanation"], "new-explanation")
        self.assertEqual(enriched[0]["audit_log"], ["existing", "path replay confirmed"])

    def test_merge_analysis_brief_includes_penetration_report_context(self) -> None:
        merged = merge_analysis_brief_with_penetration(
            {
                "score_explanation": "baseline",
                "potential_risks": [],
                "security_observations": [],
                "analysis_limitations": [],
                "attack_thinking": [],
                "next_steps": [],
            },
            {
                "executive_summary": "Penetration stage validated exploit plausibility.",
                "attack_chains": ["Chain A"],
                "reproduction_plan": ["Reproduce in test harness"],
                "analysis_limitations": ["No runtime auth tokens were available."],
                "next_steps": ["Harden query builder."],
                "benchmark": {"benchmark_summary": "Benchmarked 3 high-risk paths."},
            },
        )

        self.assertEqual(merged["score_explanation"], "baseline")
        self.assertIn("Benchmarked 3 high-risk paths.", merged["security_observations"])
        self.assertIn("Chain A", merged["attack_thinking"])
        self.assertIn("Reproduce in test harness", merged["next_steps"])
        self.assertIn("No runtime auth tokens were available.", merged["analysis_limitations"])

    def test_penetration_log_lines_prioritize_summary_benchmark_and_chains(self) -> None:
        lines = build_penetration_log_lines(
            {
                "executive_summary": "Executive summary",
                "benchmark": {"benchmark_summary": "Benchmark summary"},
                "attack_chains": ["Chain one", "Chain two", "Chain three"],
            }
        )

        self.assertEqual(lines, ["Executive summary", "Benchmark summary", "Chain one", "Chain two"])

    def test_penetration_fallback_report_keeps_coverage_and_confidence_metrics(self) -> None:
        report = build_penetration_fallback_report(
            [
                {"file": "api.py", "line": 12, "title": "SQL injection", "confidence": 90},
                {"file": "api.py", "line": 48, "title": "Command injection", "confidence": 70},
            ],
            reason="AI provider fallback (nvidia/timeout)",
        )

        self.assertEqual(report["benchmark"]["findings_covered"], 2)
        self.assertEqual(report["benchmark"]["paths_exercised"], 2)
        self.assertEqual(report["benchmark"]["confidence_average"], 80)
        self.assertIn("AI provider fallback (nvidia/timeout)", report["analysis_limitations"])
        self.assertTrue(report["benchmark"]["benchmark_summary"])

    def test_repository_map_fallback_builds_priority_paths_from_traced_paths(self) -> None:
        fallback_map = build_repository_map_fallback(
            profile={"file_count": 3, "languages": ["python"]},
            repository_artifacts={"coverage": {"route_files": 1, "auth_files": 1, "sink_candidates": 2}},
            framework_profile={"primary_framework": "fastapi"},
            traced_paths={
                "paths": [
                    {
                        "source": {"file": "api.py", "line": 10},
                        "sink": {"file": "api.py", "line": 40, "kind": "command_execution"},
                    }
                ]
            },
        )

        self.assertEqual(fallback_map["review_note"], "Repository map was generated using deterministic fallback artifacts.")
        self.assertEqual(len(fallback_map["priority_paths"]), 1)
        self.assertEqual(fallback_map["priority_paths"][0]["file"], "api.py")
        self.assertIn("Fallback map identified 1 route files", fallback_map["coverage_note"])

    def test_runtime_metrics_include_penetration_sandbox_snapshot(self) -> None:
        merged = merge_runtime_metrics_with_penetration_sandbox(
            {"latency_ms": 120},
            {
                "enabled": True,
                "mode": "isolated_copy",
                "workspace_root": "D:/sandbox/workspace",
                "manifest_path": "D:/sandbox/manifest.json",
                "copied_files": 6,
                "skipped_files": 2,
                "truncated": False,
            },
        )

        self.assertEqual(merged["latency_ms"], 120)
        self.assertTrue(merged["penetration_sandbox"]["enabled"])
        self.assertEqual(merged["penetration_sandbox"]["mode"], "isolated_copy")
        self.assertEqual(merged["penetration_sandbox"]["copied_files"], 6)

    def test_runtime_metrics_include_agent_pipeline(self) -> None:
        merged = merge_runtime_metrics_with_agent_pipeline({"latency_ms": 80})
        self.assertEqual(merged["latency_ms"], 80)
        self.assertEqual(merged["agent_pipeline"]["scan_agents"], ["DetectionAgent", "PenetrationTestAgent"])
        self.assertEqual(merged["agent_pipeline"]["remediation_agents"], ["ExplainAgent", "FixAgent", "ValidationAgent"])


if __name__ == "__main__":
    unittest.main()
