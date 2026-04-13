import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.entities.scan import FindingEntity, ScanSessionEntity
from app.infrastructure.learning.normalization import (
    normalize_external_item,
    normalize_internal_finding,
    normalize_patch_record,
    normalize_status,
)
from app.infrastructure.learning.schemas import ExternalKnowledgeSourceSpec


class LearningNormalizationTests(unittest.TestCase):
    def test_status_mapping_normalizes_known_values(self):
        self.assertEqual(normalize_status("open"), "suspected")
        self.assertEqual(normalize_status("approved"), "patch_approved")
        self.assertEqual(normalize_status("verified_fixed"), "verified_fixed")

    def test_internal_finding_normalization_has_stable_shape(self):
        now = datetime.now(timezone.utc)
        finding = FindingEntity(
            id="f-1",
            severity="high",
            title="SQL injection",
            file="api/users.py",
            line=22,
            line_end=22,
            category="sql_injection",
            confidence=91,
            summary="Unsafe query",
            impact="DB compromise",
            attack_input="POST /users",
            attack_execution="request -> sql",
            attack_result="data leak",
            audit_log=["log"],
            explanation="expl",
            fix_suggestions=[],
            evidence="query = f\"...\"",
            remediation_status="patch_generated",
            approval_status="pending",
        )
        session = ScanSessionEntity(
            id="session-1",
            title="scan",
            repo="repo",
            source_path="D:/repo",
            target_type="folder",
            preset="balanced",
            scan_mode="deep",
            status="completed",
            progress=100,
            progress_message="done",
            current_phase="done",
            elapsed_seconds=10,
            preview="preview",
            source_fingerprint="abc123",
            findings=[finding],
            framework_profile={"frameworks": ["fastapi"]},
        )
        normalized = normalize_internal_finding(
            session=session,
            finding=finding,
            source_system="internal_scans",
            now=now,
        )
        self.assertEqual(normalized.record_type, "finding")
        self.assertEqual(normalized.status, "patch_generated")
        self.assertEqual(normalized.framework, "fastapi")
        self.assertTrue(normalized.content_fingerprint)

    def test_patch_record_is_emitted_for_patch_generated(self):
        now = datetime.now(timezone.utc)
        finding = FindingEntity(
            id="f-2",
            severity="medium",
            title="xss",
            file="web/app.ts",
            line=10,
            line_end=10,
            category="xss",
            confidence=78,
            summary="unsafe html",
            impact="session theft",
            attack_input="query param",
            attack_execution="input -> sink",
            attack_result="script execution",
            audit_log=[],
            explanation="",
            fix_suggestions=[],
            evidence="<div>{input}</div>",
            remediation_status="patch_generated",
            approval_status="approved",
        )
        session = ScanSessionEntity(
            id="session-2",
            title="scan",
            repo="repo",
            source_path="D:/repo",
            target_type="folder",
            preset="balanced",
            scan_mode="deep",
            status="completed",
            progress=100,
            progress_message="done",
            current_phase="done",
            elapsed_seconds=10,
            preview="preview",
            source_fingerprint="xyz987",
            findings=[finding],
        )
        patch = normalize_patch_record(session=session, finding=finding, source_system="internal_scans", now=now)
        self.assertIsNotNone(patch)
        assert patch is not None
        self.assertIn(patch.status, {"patch_generated", "patch_approved"})

    def test_external_item_normalization_for_security_pattern(self):
        source = ExternalKnowledgeSourceSpec(
            source_name="cwe",
            source_version="4.14",
            endpoint="https://example.test/cwe.json",
            item_type="security_pattern",
            language="python",
            framework="fastapi",
            vulnerability_category="sql_injection",
            weakness_id="CWE-89",
        )
        normalized = normalize_external_item(
            source=source,
            raw_item={
                "title": "SQL Injection",
                "summary": "Dynamic query",
                "unsafe_pattern": "f\"SELECT ... {user}\"",
                "safe_pattern": "parameterized query",
                "tags": ["database", "injection"],
            },
            ingestion_run_id="run-1",
        )
        self.assertEqual(normalized.record_type, "security_pattern")
        self.assertEqual(normalized.weakness_id, "CWE-89")
        self.assertTrue(normalized.content_fingerprint)


if __name__ == "__main__":
    unittest.main()
