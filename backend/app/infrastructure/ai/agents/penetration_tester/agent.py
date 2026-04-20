from __future__ import annotations

from app.infrastructure.ai.agents.penetration_tester.contracts import PenetrationReport


class PenetrationTestAgent:
    def __init__(self, ai_client) -> None:
        self.ai_client = ai_client

    async def run(self, penetration_context: dict) -> PenetrationReport:
        runner = getattr(self.ai_client, "run_penetration_test", None)
        if not callable(runner):
            return {
                "review_note": "",
                "executive_summary": "",
                "attack_chains": [],
                "reproduction_plan": [],
                "analysis_limitations": [],
                "next_steps": [],
                "benchmark": {
                    "findings_covered": 0,
                    "paths_exercised": 0,
                    "confidence_average": 0,
                    "benchmark_summary": "",
                },
                "finding_overrides": [],
            }
        return await runner(penetration_context)
