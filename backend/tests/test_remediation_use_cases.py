import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application.dto.remediation_contracts import ExplainFindingRequest, GenerateFixRequest
from app.application.dto.remediation_contracts import ApplyFixRequest, GenerateBatchRemediationRequest, RejectFixRequest, RetryFixStrategyRequest
from app.application.use_cases.apply_fix import ApplyFixUseCase
from app.application.use_cases.explain_finding import ExplainFindingUseCase
from app.application.use_cases.generate_batch_remediation import GenerateBatchRemediationUseCase
from app.application.use_cases.generate_fix import GenerateFixUseCase
from app.application.use_cases.reject_fix import RejectFixUseCase
from app.application.use_cases.retry_fix_strategy import RetryFixStrategyUseCase
from app.domain.entities.scan import FindingEntity, ScanSessionEntity
from app.core.exceptions import WorkflowConflictError


class FakeRepository:
    def __init__(self, session: ScanSessionEntity) -> None:
        self.session = session

    async def create(self, session):
        self.session = session
        return session

    async def update(self, session_id, updates):
        if self.session.id != session_id:
            return None
        for key, value in updates.items():
            if key in {"findings", "candidate_findings"}:
                value = [
                    item if isinstance(item, FindingEntity) else FindingEntity(**item)
                    for item in value
                ]
            setattr(self.session, key, value)
        return self.session

    async def get_by_id(self, session_id):
        return self.session if self.session.id == session_id else None

    async def list_recent(self, limit: int = 25):
        return [self.session][:limit]

    async def delete(self, session_id):
        return self.session.id == session_id

    async def delete_all(self):
        return 1


class FakeAgentRouter:
    async def start_run(self, remediation_context: dict, mode: str) -> None:
        return None

    async def build_trace(self, remediation_context: dict, mode: str):
        return [
            type("Task", (), {"task_name": "context_shape", "label": "Building remediation context", "agent": "context_agent", "details": []})(),
            type("Task", (), {"task_name": "explain_draft", "label": "Analyzing vulnerability", "agent": "explain_agent", "details": []})(),
            type("Task", (), {"task_name": "fix_draft", "label": "Generating fix strategies", "agent": "fix_agent", "details": []})(),
            type("Task", (), {"task_name": "fix_validate", "label": "Validating fixes", "agent": "validation_agent", "details": []})(),
            type("Task", (), {"task_name": "final_patch", "label": "Preparing review-ready patch", "agent": "fix_agent", "details": []})(),
        ]

    async def explain(self, remediation_context: dict, *, mode: str = "single") -> dict:
        return {
            "summary": f"Exploit path for {remediation_context['finding']['title']}",
            "exploit_scenario": "An attacker can reach the query builder through the login route.",
            "request_example": "POST /login",
            "payload_example": "{\"email\": \"a' OR '1'='1\"}",
            "attack_steps": [
                "Submit crafted credentials to the login endpoint.",
                "Reach the unsafe dynamic query construction.",
                "Bypass the intended lookup controls.",
            ],
            "entry_point": "/login",
            "execution_path": "router -> service -> query builder",
            "sink": "app/features/login/router.py:43",
            "impact": "Authentication logic can be abused through SQL injection.",
        }

    async def generate_fix(self, remediation_context: dict, mode: str) -> dict:
        excluded = set(remediation_context.get("retry", {}).get("excluded_strategy_ids", []))
        strategies = [
            {
                "id": "parameterized-query",
                "label": "Parameterized query",
                "kind": "refactor",
                "confidence": 92,
                "impact": "high",
                "effort": "medium",
                "summary": "Replace string interpolation with a bound parameter query.",
                "rationale": "The traced sink is a dynamic SQL execution path.",
                "diff": "--- a/app/features/login/router.py\n+++ b/app/features/login/router.py\n@@\n-query = f\"SELECT * FROM users WHERE email = '{email}'\"\n+query = \"SELECT * FROM users WHERE email = %s\"\n+cursor.execute(query, (email,))",
                "recommended": True,
            },
            {
                "id": "allowlist-guard",
                "label": "Allowlist guard",
                "kind": "guard",
                "confidence": 78,
                "impact": "medium",
                "effort": "low",
                "summary": "Reject unexpected email patterns before the query builder.",
                "rationale": "Adds a trust-boundary guard ahead of the sink.",
                "diff": "--- a/app/features/login/router.py\n+++ b/app/features/login/router.py\n@@\n+if \"'\" in email:\n+    raise ValueError(\"invalid email\")",
                "recommended": False,
            },
        ]
        strategies = [item for item in strategies if item["id"] not in excluded]
        return {
            "review_summary": f"Prepared a {mode} remediation plan.",
            "recommended_strategy_id": strategies[0]["id"] if strategies else None,
            "strategies": strategies,
            "patch": {
                "file": "app/features/login/router.py",
                "language": "python",
                "summary": "Parameterize the user lookup query.",
                "diff": "--- a/app/features/login/router.py\n+++ b/app/features/login/router.py\n@@\n-query = f\"SELECT * FROM users WHERE email = '{email}'\"\n+query = \"SELECT * FROM users WHERE email = %s\"\n+cursor.execute(query, (email,))",
                "validation_notes": [
                    "The patch modifies the traced sink.",
                    "The patch preserves the surrounding login flow.",
                ],
                "before_snippet": "query = f\"SELECT * FROM users WHERE email = '{email}'\"",
                "after_snippet": "query = \"SELECT * FROM users WHERE email = %s\"\ncursor.execute(query, (email,))",
            },
        }


class StaticRuntimeSettingsService:
    def __init__(self, *, remediation_max_attempts: int, remediation_reuse_explanation: bool) -> None:
        self.remediation_max_attempts = remediation_max_attempts
        self.remediation_reuse_explanation = remediation_reuse_explanation

    async def get(self):
        return self


class RetryingAgentRouter(FakeAgentRouter):
    def __init__(self) -> None:
        self.explain_calls = 0
        self.fix_calls = 0

    async def explain(self, remediation_context: dict, *, mode: str = "single") -> dict:
        self.explain_calls += 1
        return await super().explain(remediation_context, mode=mode)

    async def generate_fix(self, remediation_context: dict, mode: str) -> dict:
        self.fix_calls += 1
        strategy_id = f"guard-{self.fix_calls}"
        return {
            "review_summary": f"Retry candidate {self.fix_calls}",
            "recommended_strategy_id": strategy_id,
            "strategies": [
                {
                    "id": strategy_id,
                    "label": "Guard-only remediation",
                    "kind": "guard",
                    "confidence": 62,
                    "impact": "low",
                    "effort": "low",
                    "summary": "Adds a shallow guard before the sink.",
                    "rationale": "Temporary stop-gap control.",
                    "diff": "--- a/app/features/login/router.py\n+++ b/app/features/login/router.py\n@@\n+if \"'\" in email:\n+    raise ValueError(\"invalid email\")",
                    "recommended": True,
                }
            ],
            "patch": {
                "file": "app/features/login/router.py",
                "language": "python",
                "summary": "Guard-only patch candidate.",
                "diff": "--- a/app/features/login/router.py\n+++ b/app/features/login/router.py\n@@\n+if \"'\" in email:\n+    raise ValueError(\"invalid email\")",
                "validation_notes": ["Guard-only strategy candidate."],
                "before_snippet": "query = f\"SELECT * FROM users WHERE email = '{email}'\"",
                "after_snippet": "if \"'\" in email:\n    raise ValueError(\"invalid email\")",
            },
        }


class RemediationUseCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        target = root / "app" / "features" / "login"
        target.mkdir(parents=True, exist_ok=True)
        self.file_path = target / "router.py"
        self.file_path.write_text(
            "async def login(email):\n"
            "    query = f\"SELECT * FROM users WHERE email = '{email}'\"\n"
            "    return run_query(query)\n",
            encoding="utf-8",
        )

        finding = FindingEntity(
            id="finding-1",
            severity="high",
            title="Dynamic query construction may allow injection",
            file="app/features/login/router.py",
            line=2,
            line_end=2,
            category="SQL injection",
            confidence=79,
            summary="A dynamic query is built from untrusted input.",
            impact="Login lookup may be vulnerable to injection.",
            attack_input="POST /login",
            attack_execution="router -> service -> query builder",
            attack_result="Authentication logic may be bypassed.",
            audit_log=["Matched SQL sink", "Queued for remediation"],
            explanation="User input reaches a dynamic SQL sink.",
            fix_suggestions=[],
            evidence="query = f\"SELECT * FROM users WHERE email = '{email}'\"",
        )
        self.session = ScanSessionEntity(
            id="session-1",
            title="Scan backend",
            repo="backend",
            source_path=str(root),
            target_type="folder",
            preset="balanced",
            scan_mode="deep",
            status="completed",
            progress=100,
            progress_message="Completed",
            current_phase="Reporting",
            elapsed_seconds=12,
            preview="preview",
            findings=[finding],
            path_inventory={
                "paths": [
                    {
                        "path_hint": "POST /login -> router -> query builder",
                        "path_type": "intra_file",
                        "source": {"file": "app/features/login/router.py", "line": 1},
                        "sink": {"file": "app/features/login/router.py", "line": 2},
                        "line_sequence": [1, 2],
                    }
                ]
            },
        )
        self.repository = FakeRepository(self.session)
        self.router = FakeAgentRouter()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_explain_finding_returns_code_aware_explanation(self):
        use_case = ExplainFindingUseCase(self.repository, self.router)

        response = asyncio.run(use_case.execute(ExplainFindingRequest(session_id="session-1", finding_id="finding-1")))

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response.finding_id, "finding-1")
        self.assertEqual(response.entry_point, "/login")
        self.assertIn("query builder", response.execution_path)
        self.assertEqual(len(response.attack_steps), 3)

    def test_generate_fix_returns_strategy_and_patch_diff(self):
        use_case = GenerateFixUseCase(self.repository, self.router)

        response = asyncio.run(use_case.execute(GenerateFixRequest(session_id="session-1", finding_id="finding-1")))

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response.mode, "single")
        self.assertEqual(response.recommended_strategy_id, "parameterized-query")
        self.assertEqual(response.patch.file, "app/features/login/router.py")
        self.assertIn("cursor.execute", response.patch.after_snippet)
        self.assertTrue(response.strategies[0].recommended)
        self.assertEqual(response.strategies[0].fix_type, "full_fix")
        self.assertEqual(response.strategies[0].security_strength, "high")
        self.assertEqual(response.strategies[1].fix_type, "risky_workaround")
        self.assertIn("parameterization", " ".join(response.patch.validation_notes).lower())
        self.assertIsNotNone(response.score)
        self.assertGreaterEqual(response.score.total, 70)
        self.assertGreaterEqual(response.score.strategy_quality, 80)
        self.assertGreaterEqual(response.metrics.analyzed_lines, 1)
        self.assertEqual(response.metrics.path_steps, 2)
        self.assertEqual(len(response.steps), 5)

    def test_generate_fix_reuses_explanation_when_enabled(self):
        router = RetryingAgentRouter()
        use_case = GenerateFixUseCase(
            self.repository,
            router,
            runtime_settings_service=StaticRuntimeSettingsService(
                remediation_max_attempts=2,
                remediation_reuse_explanation=True,
            ),
        )

        response = asyncio.run(use_case.execute(GenerateFixRequest(session_id="session-1", finding_id="finding-1")))

        self.assertIsNotNone(response)
        self.assertEqual(router.fix_calls, 2)
        self.assertEqual(router.explain_calls, 1)

    def test_generate_fix_calls_explain_each_attempt_when_reuse_is_disabled(self):
        router = RetryingAgentRouter()
        use_case = GenerateFixUseCase(
            self.repository,
            router,
            runtime_settings_service=StaticRuntimeSettingsService(
                remediation_max_attempts=2,
                remediation_reuse_explanation=False,
            ),
        )

        response = asyncio.run(use_case.execute(GenerateFixRequest(session_id="session-1", finding_id="finding-1")))

        self.assertIsNotNone(response)
        self.assertEqual(router.fix_calls, 2)
        self.assertEqual(router.explain_calls, 2)

    def test_generate_fix_does_not_apply_patch_before_approval(self):
        original = self.file_path.read_text(encoding="utf-8")
        use_case = GenerateFixUseCase(self.repository, self.router)

        response = asyncio.run(use_case.execute(GenerateFixRequest(session_id="session-1", finding_id="finding-1")))

        assert response is not None
        self.assertEqual(self.file_path.read_text(encoding="utf-8"), original)
        self.assertEqual(self.session.findings[0].remediation_status, "patch_generated")
        self.assertEqual(self.session.findings[0].approval_status, "pending")
        self.assertIsNone(self.session.findings[0].applied_strategy_id)


    def test_apply_fix_writes_patch_to_disk(self):
        use_case = ApplyFixUseCase(self.repository)

        response = asyncio.run(use_case.execute(
            ApplyFixRequest(
                session_id="session-1",
                finding_id="finding-1",
                strategy_id="parameterized-query",
                file="app/features/login/router.py",
                before_snippet="query = f\"SELECT * FROM users WHERE email = '{email}'\"",
                after_snippet="query = \"SELECT * FROM users WHERE email = %s\"\ncursor.execute(query, (email,))",
                diff="--- a/app/features/login/router.py\n+++ b/app/features/login/router.py",
                manual_edit=False,
                approval_acknowledged=True,
                mode="single",
            )
        ))

        assert response is not None
        self.assertEqual(response.action.status, "applied")
        self.assertIn("cursor.execute", self.file_path.read_text(encoding="utf-8"))
        self.assertEqual(response.action.verification_status, "verified")
        self.assertTrue(response.action.rollback_available)
        self.assertEqual(response.action.approval_gate_outcome, "review-required")
        self.assertEqual(len(response.findings), 0)
        self.assertEqual(len(self.session.remediation_checkpoints), 1)

    def test_apply_fix_keeps_finding_open_when_verification_requires_review(self):
        self.file_path.write_text(
            "async def login(email):\n"
            "    query = f\"SELECT * FROM users WHERE email = '{email}'\"\n"
            "    return db.execute(query)\n",
            encoding="utf-8",
        )
        use_case = ApplyFixUseCase(self.repository)

        response = asyncio.run(use_case.execute(
            ApplyFixRequest(
                session_id="session-1",
                finding_id="finding-1",
                strategy_id="allowlist-guard",
                file="app/features/login/router.py",
                before_snippet="query = f\"SELECT * FROM users WHERE email = '{email}'\"",
                after_snippet="query = f\"SELECT * FROM users WHERE email = '{email.strip()}'\"",
                diff="--- a/app/features/login/router.py\n+++ b/app/features/login/router.py",
                manual_edit=False,
                approval_acknowledged=True,
                mode="single",
            )
        ))

        assert response is not None
        self.assertEqual(response.action.status, "applied")
        self.assertEqual(response.action.verification_status, "manual_review_required")
        self.assertEqual(response.findings[0].remediation_status, "verified_partial")
        self.assertEqual(len(response.findings), 1)

    def test_rollback_restores_original_file_and_session_state(self):
        apply_use_case = ApplyFixUseCase(self.repository)
        apply_response = asyncio.run(apply_use_case.execute(
            ApplyFixRequest(
                session_id="session-1",
                finding_id="finding-1",
                strategy_id="parameterized-query",
                file="app/features/login/router.py",
                before_snippet="query = f\"SELECT * FROM users WHERE email = '{email}'\"",
                after_snippet="query = \"SELECT * FROM users WHERE email = %s\"\ncursor.execute(query, (email,))",
                diff="--- a/app/features/login/router.py\n+++ b/app/features/login/router.py",
                manual_edit=False,
                approval_acknowledged=True,
                mode="single",
            )
        ))
        assert apply_response is not None
        checkpoint_id = apply_response.action.checkpoint_id
        from app.application.dto.remediation_contracts import RollbackFixRequest
        from app.application.use_cases.rollback_fix import RollbackFixUseCase

        rollback_use_case = RollbackFixUseCase(self.repository)
        rollback_response = asyncio.run(rollback_use_case.execute(
            RollbackFixRequest(
                session_id="session-1",
                finding_id="finding-1",
                checkpoint_id=checkpoint_id,
            )
        ))

        assert rollback_response is not None
        self.assertEqual(rollback_response.action.status, "rolled_back")
        self.assertIn("query = f", self.file_path.read_text(encoding="utf-8"))
        self.assertEqual(len(rollback_response.findings), 1)

    def test_reject_fix_applies_no_changes(self):
        original = self.file_path.read_text(encoding="utf-8")
        use_case = RejectFixUseCase(self.repository)

        response = asyncio.run(use_case.execute(
            RejectFixRequest(
                session_id="session-1",
                finding_id="finding-1",
                strategy_id="parameterized-query",
            )
        ))

        assert response is not None
        self.assertEqual(response.action.status, "rejected")
        self.assertEqual(self.file_path.read_text(encoding="utf-8"), original)

    def test_retry_fix_excludes_previous_strategy(self):
        use_case = RetryFixStrategyUseCase(self.repository, self.router)

        response = asyncio.run(use_case.execute(
            RetryFixStrategyRequest(
                session_id="session-1",
                finding_id="finding-1",
                mode="single",
                excluded_strategy_ids=["parameterized-query"],
                attempted_strategy_ids=["parameterized-query"],
            )
        ))

        assert response is not None
        self.assertEqual(response.recommended_strategy_id, "allowlist-guard")
        self.assertNotEqual(response.strategies[0].id, "parameterized-query")

    def test_generate_batch_remediation_builds_multi_finding_plan(self):
        second = FindingEntity(
            id="finding-2",
            severity="medium",
            title="Redirect target may be user-controlled",
            file="app/features/login/router.py",
            line=3,
            line_end=3,
            category="Open redirect",
            confidence=67,
            summary="Redirect flow may trust unvalidated input.",
            impact="Redirect behavior may be abused.",
            attack_input="GET /redirect?next=",
            attack_execution="router -> redirect helper",
            attack_result="Users may be sent to attacker-controlled destinations.",
            audit_log=["Matched redirect sink"],
            explanation="Untrusted redirect target flows into a redirect helper.",
            fix_suggestions=[],
            evidence="return redirect(next_url)",
        )
        self.session.findings.append(second)
        use_case = GenerateBatchRemediationUseCase(self.repository, self.router)

        response = asyncio.run(use_case.execute(GenerateBatchRemediationRequest(session_id="session-1")))

        assert response is not None
        self.assertEqual(response.mode, "batch")
        self.assertEqual(len(response.finding_ids), 2)
        self.assertIn("2 validated findings", response.review_summary)
        self.assertEqual(response.patch.file, "app/features/login/router.py")

    def test_apply_fix_requires_approval_acknowledgement_for_high_risk_path(self):
        use_case = ApplyFixUseCase(self.repository)

        with self.assertRaises(WorkflowConflictError):
            asyncio.run(use_case.execute(
                ApplyFixRequest(
                    session_id="session-1",
                    finding_id="finding-1",
                    strategy_id="parameterized-query",
                    file="app/features/login/router.py",
                    before_snippet="query = f\"SELECT * FROM users WHERE email = '{email}'\"",
                    after_snippet="query = \"SELECT * FROM users WHERE email = %s\"\ncursor.execute(query, (email,))",
                    diff="--- a/app/features/login/router.py\n+++ b/app/features/login/router.py",
                    manual_edit=False,
                    mode="single",
                )
            ))


if __name__ == "__main__":
    unittest.main()
