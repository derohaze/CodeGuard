from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domain.entities.scan import FindingEntity, ScanSessionEntity
from app.infrastructure.learning.fingerprints import bounded_identifier, stable_fingerprint
from app.infrastructure.learning.schemas import (
    ExternalKnowledgeSourceSpec,
    NormalizedFeedbackEvent,
    NormalizedFindingRecord,
    NormalizedFrameworkRule,
    NormalizedPatchRecord,
    NormalizedSecurityPattern,
    StatusVocabulary,
)


RAW_TO_CANONICAL_STATUS: dict[str, StatusVocabulary] = {
    "open": "suspected",
    "patch_generated": "patch_generated",
    "applied": "applied",
    "verified_fixed": "verified_fixed",
    "verified_partial": "verified_partial",
    "validation_failed": "validation_failed",
    "rejected": "rejected",
    "rolled_back": "rolled_back",
    "pending": "candidate",
    "approved": "patch_approved",
    "not_required": "validated",
    "candidate": "candidate",
    "validated": "validated",
    "false_positive": "false_positive",
}


def normalize_status(raw_status: str | None, *, default: StatusVocabulary = "suspected") -> StatusVocabulary:
    if not raw_status:
        return default
    normalized = RAW_TO_CANONICAL_STATUS.get(raw_status.strip().lower())
    return normalized or default


def normalize_internal_finding(
    *,
    session: ScanSessionEntity,
    finding: FindingEntity,
    source_system: str,
    now: datetime,
) -> NormalizedFindingRecord:
    combined_status = normalize_status(finding.remediation_status, default="validated")
    if finding.approval_status == "rejected":
        combined_status = "patch_rejected"
    elif finding.approval_status == "approved" and combined_status == "patch_generated":
        combined_status = "patch_approved"
    elif finding.approval_status == "pending" and combined_status in {"suspected", "candidate", "validated"}:
        combined_status = "candidate"

    payload = {
        "session_id": session.id,
        "finding_id": finding.id,
        "file": finding.file,
        "line": finding.line,
        "title": finding.title,
        "category": finding.category,
        "status": combined_status,
    }
    return NormalizedFindingRecord(
        record_id=bounded_identifier("finding", payload),
        source_system=source_system,
        status=combined_status,
        created_at=session.created_at,
        updated_at=now,
        language=_infer_language_from_path(finding.file),
        framework=_extract_framework_hint(session.framework_profile),
        repository_fingerprint=session.source_fingerprint,
        file_paths=[finding.file],
        vulnerability_category=finding.category,
        severity=finding.severity,
        confidence=finding.confidence,
        source_metadata={"attack_input": finding.attack_input},
        sink_metadata={"attack_result": finding.attack_result},
        sanitizer_metadata={},
        path_metadata={"attack_execution": finding.attack_execution},
        evidence_metadata={"evidence": finding.evidence, "audit_log_size": len(finding.audit_log)},
        remediation_metadata={
            "fix_suggestions": finding.fix_suggestions,
            "applied_strategy_id": finding.applied_strategy_id,
            "attempted_strategy_ids": finding.attempted_strategy_ids,
        },
        human_outcome={"approval_status": finding.approval_status, "approval_history": finding.approval_history},
        verification_outcome={"last_verification": session.last_verification},
        raw_reference={"session_id": session.id, "finding_id": finding.id},
        tags=[finding.category, finding.severity],
        content_fingerprint=stable_fingerprint(payload),
    )


def normalize_patch_record(
    *,
    session: ScanSessionEntity,
    finding: FindingEntity,
    source_system: str,
    now: datetime,
) -> NormalizedPatchRecord | None:
    patch_status = normalize_status(finding.remediation_status, default="suspected")
    if patch_status in {"suspected", "candidate", "validated"}:
        return None

    payload = {
        "session_id": session.id,
        "finding_id": finding.id,
        "status": patch_status,
        "strategy": finding.applied_strategy_id,
    }
    return NormalizedPatchRecord(
        record_id=bounded_identifier("patch", payload),
        source_system=source_system,
        status=patch_status,
        created_at=session.created_at,
        updated_at=now,
        language=_infer_language_from_path(finding.file),
        framework=_extract_framework_hint(session.framework_profile),
        repository_fingerprint=session.source_fingerprint,
        vulnerability_category=finding.category,
        severity=finding.severity,
        confidence=finding.confidence,
        file_paths=[finding.file],
        remediation_metadata={
            "applied_strategy_id": finding.applied_strategy_id,
            "candidate_strategy_ids": [item.get("id") for item in finding.fix_suggestions if isinstance(item, dict)],
            "notes": finding.remediation_notes,
        },
        verification_outcome={"last_verification": session.last_verification},
        human_outcome={"approval_status": finding.approval_status},
        raw_reference={"session_id": session.id, "finding_id": finding.id},
        tags=[finding.category, patch_status],
        content_fingerprint=stable_fingerprint(payload),
    )


def normalize_feedback_event(raw_event: dict[str, Any]) -> NormalizedFeedbackEvent:
    payload = {
        "event_id": raw_event.get("event_id"),
        "session_id": raw_event.get("session_id"),
        "finding_id": raw_event.get("finding_id"),
        "patch_id": raw_event.get("patch_id"),
        "status": raw_event.get("status"),
        "outcome": raw_event.get("outcome"),
    }
    return NormalizedFeedbackEvent(
        event_id=str(raw_event.get("event_id") or bounded_identifier("feedback", payload)),
        source_system=str(raw_event.get("source_system") or "manual_feedback"),
        created_at=raw_event.get("created_at") or datetime.utcnow(),
        status=normalize_status(str(raw_event.get("status") or "candidate"), default="candidate"),
        session_id=raw_event.get("session_id"),
        finding_id=raw_event.get("finding_id"),
        patch_id=raw_event.get("patch_id"),
        actor_type=str(raw_event.get("actor_type") or "human_reviewer"),
        outcome=raw_event.get("outcome"),
        notes=raw_event.get("notes"),
        repository_fingerprint=raw_event.get("repository_fingerprint"),
        language=raw_event.get("language"),
        framework=raw_event.get("framework"),
        vulnerability_category=raw_event.get("vulnerability_category"),
        raw_reference={"feedback_source": raw_event.get("source")},
        content_fingerprint=stable_fingerprint(payload),
    )


def normalize_external_item(
    *,
    source: ExternalKnowledgeSourceSpec,
    raw_item: dict[str, Any],
    ingestion_run_id: str,
) -> NormalizedSecurityPattern | NormalizedFrameworkRule:
    normalized_payload = {
        "source_name": source.source_name,
        "source_version": source.source_version,
        "weakness_id": raw_item.get("weakness_id") or source.weakness_id,
        "title": raw_item.get("title") or "Untitled security knowledge",
        "summary": raw_item.get("summary") or raw_item.get("description") or "",
        "language": raw_item.get("language") or source.language,
        "framework": raw_item.get("framework") or source.framework,
        "vulnerability_category": raw_item.get("vulnerability_category") or source.vulnerability_category,
        "item_type": raw_item.get("item_type") or source.item_type,
    }
    item_fingerprint = stable_fingerprint(normalized_payload)
    common = {
        "source_name": source.source_name,
        "source_version": source.source_version,
        "item_type": str(normalized_payload["item_type"]),
        "language": normalized_payload["language"],
        "framework": normalized_payload["framework"],
        "vulnerability_category": normalized_payload["vulnerability_category"],
        "weakness_id": normalized_payload["weakness_id"],
        "title": str(normalized_payload["title"]),
        "summary": str(normalized_payload["summary"] or ""),
        "tags": _merge_tags(source.tags, raw_item.get("tags")),
        "original_reference": raw_item.get("original_reference") or source.original_reference or source.endpoint,
        "raw_reference": {"ingestion_run_id": ingestion_run_id},
        "content_fingerprint": item_fingerprint,
    }
    item_type = str(normalized_payload["item_type"]).lower()
    if item_type in {"framework_rule", "rule", "query_rule"}:
        return NormalizedFrameworkRule(
            rule_id=bounded_identifier("fwrule", normalized_payload),
            **common,
        )

    return NormalizedSecurityPattern(
        pattern_id=bounded_identifier("pattern", normalized_payload),
        unsafe_pattern=raw_item.get("unsafe_pattern"),
        safe_pattern=raw_item.get("safe_pattern"),
        bad_example=raw_item.get("bad_example"),
        good_example=raw_item.get("good_example"),
        remediation_notes=raw_item.get("remediation_notes"),
        license_notes=raw_item.get("license_notes") or source.license_notes,
        **common,
    )


def _merge_tags(source_tags: list[str], item_tags: Any) -> list[str]:
    tags = {str(tag).strip().lower() for tag in source_tags if str(tag).strip()}
    if isinstance(item_tags, list):
        for tag in item_tags:
            normalized = str(tag).strip().lower()
            if normalized:
                tags.add(normalized)
    return sorted(tags)


def _infer_language_from_path(file_path: str) -> str | None:
    lowered = file_path.lower()
    if lowered.endswith(".py"):
        return "python"
    if lowered.endswith(".ts") or lowered.endswith(".tsx"):
        return "typescript"
    if lowered.endswith(".js") or lowered.endswith(".jsx"):
        return "javascript"
    if lowered.endswith(".java"):
        return "java"
    if lowered.endswith(".go"):
        return "go"
    if lowered.endswith(".rb"):
        return "ruby"
    if lowered.endswith(".php"):
        return "php"
    return None


def _extract_framework_hint(framework_profile: dict | None) -> str | None:
    if not framework_profile:
        return None
    primary = framework_profile.get("primary_framework")
    if isinstance(primary, str) and primary and primary != "unknown":
        return primary.lower()
    frameworks = framework_profile.get("frameworks")
    if isinstance(frameworks, list):
        for item in frameworks:
            if isinstance(item, str) and item and item != "unknown":
                return item.lower()
    return None

