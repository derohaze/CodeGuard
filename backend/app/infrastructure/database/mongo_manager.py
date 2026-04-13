from __future__ import annotations

from pathlib import Path

from pymongo import DESCENDING

from app.core.config import get_settings
from app.infrastructure.database.collections import (
    AUDIT_EVENTS_COLLECTION,
    FINDINGS_COLLECTION,
    FIX_SUGGESTIONS_COLLECTION,
    REPORT_EXPORTS_COLLECTION,
    REQUIRED_COLLECTIONS,
    SCAN_JOBS_COLLECTION,
    SCAN_SESSIONS_COLLECTION,
    VERIFICATION_RUNS_COLLECTION,
)
from app.infrastructure.database.mongo import get_database


async def ensure_mongo_collections() -> None:
    database = get_database()
    existing = set(await database.list_collection_names())
    for collection_name in REQUIRED_COLLECTIONS:
        if collection_name not in existing:
            await database.create_collection(collection_name)


async def ensure_mongo_indexes() -> None:
    database = get_database()
    scan_sessions = database[SCAN_SESSIONS_COLLECTION]
    async for document in scan_sessions.find(
        {"$or": [{"session_id": {"$exists": False}}, {"session_id": None}]},
        {"_id": 1},
    ):
        await scan_sessions.update_one(
            {"_id": document["_id"]},
            {"$set": {"session_id": str(document["_id"])}},
        )
    await scan_sessions.create_index([("updated_at", DESCENDING)], name="idx_scan_sessions_updated_at_desc")
    await scan_sessions.create_index([("status", 1), ("updated_at", DESCENDING)], name="idx_scan_sessions_status_updated_at_desc")
    await scan_sessions.create_index([("repo", 1), ("updated_at", DESCENDING)], name="idx_scan_sessions_repo_updated_at_desc")
    await scan_sessions.create_index([("session_id", 1)], name="ux_scan_sessions_session_id", unique=True)

    scan_jobs = database[SCAN_JOBS_COLLECTION]
    async for document in scan_jobs.find(
        {"$or": [{"job_id": {"$exists": False}}, {"job_id": None}]},
        {"_id": 1},
    ):
        await scan_jobs.update_one(
            {"_id": document["_id"]},
            {"$set": {"job_id": str(document["_id"])}},
        )
    await scan_jobs.create_index([("job_id", 1)], name="ux_scan_jobs_job_id", unique=True)
    await scan_jobs.create_index([("session_id", 1), ("created_at", DESCENDING)], name="idx_scan_jobs_session_created_at_desc")
    await scan_jobs.create_index([("status", 1), ("created_at", DESCENDING)], name="idx_scan_jobs_status_created_at_desc")
    await scan_jobs.create_index(
        [("source_fingerprint", 1), ("status", 1), ("created_at", DESCENDING)],
        name="idx_scan_jobs_source_status_created_at_desc",
    )

    findings = database[FINDINGS_COLLECTION]
    await findings.update_many(
        {"finding_kind": {"$exists": False}},
        {"$set": {"finding_kind": "validated"}},
    )
    existing_finding_indexes = await findings.index_information()
    if "ux_findings_finding_id" in existing_finding_indexes:
        await findings.drop_index("ux_findings_finding_id")
    await findings.create_index([("session_id", 1), ("finding_kind", 1), ("finding_id", 1)], name="ux_findings_session_kind_finding_id", unique=True)
    await findings.create_index([("session_id", 1), ("severity", 1)], name="idx_findings_session_severity")
    await findings.create_index([("scan_job_id", 1)], name="idx_findings_scan_job_id")
    await findings.create_index([("fingerprint", 1)], name="idx_findings_fingerprint")

    fix_suggestions = database[FIX_SUGGESTIONS_COLLECTION]
    await fix_suggestions.create_index([("fix_id", 1)], name="ux_fix_suggestions_fix_id", unique=True)
    await fix_suggestions.create_index([("finding_id", 1), ("created_at", DESCENDING)], name="idx_fix_suggestions_finding_created_at_desc")

    verification_runs = database[VERIFICATION_RUNS_COLLECTION]
    await verification_runs.create_index([("verification_id", 1)], name="ux_verification_runs_verification_id", unique=True)
    await verification_runs.create_index([("fix_id", 1), ("created_at", DESCENDING)], name="idx_verification_runs_fix_created_at_desc")

    audit_events = database[AUDIT_EVENTS_COLLECTION]
    await audit_events.create_index([("entity_type", 1), ("entity_id", 1), ("created_at", DESCENDING)], name="idx_audit_events_entity_created_at_desc")

    report_exports = database[REPORT_EXPORTS_COLLECTION]
    await report_exports.create_index([("session_id", 1), ("created_at", DESCENDING)], name="idx_report_exports_session_created_at_desc")


def ensure_artifacts_directory() -> Path:
    artifacts_dir = Path(get_settings().artifacts_dir).expanduser().resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


async def ensure_backend_bootstrap() -> None:
    await ensure_mongo_collections()
    await ensure_mongo_indexes()
    ensure_artifacts_directory()
