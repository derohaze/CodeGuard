from __future__ import annotations

from pathlib import Path

from pymongo import DESCENDING

from app.core.config import get_settings
from app.infrastructure.database.collections import (
    AUDIT_EVENTS_COLLECTION,
    BENCHMARK_CASES_COLLECTION,
    BENCHMARK_RUNS_COLLECTION,
    BENCHMARK_SUITES_COLLECTION,
    BUILDER_MEMORY_ITEMS_COLLECTION,
    BUILDER_MESSAGES_COLLECTION,
    BUILDER_THREAD_CONTEXTS_COLLECTION,
    BUILDER_THREADS_COLLECTION,
    BUILDER_WORKSPACES_COLLECTION,
    EXTERNAL_KNOWLEDGE_CHUNKS_COLLECTION,
    EXTERNAL_KNOWLEDGE_ITEMS_COLLECTION,
    EXTERNAL_KNOWLEDGE_SOURCES_COLLECTION,
    FEEDBACK_EVENTS_COLLECTION,
    FINDINGS_COLLECTION,
    FIX_SUGGESTIONS_COLLECTION,
    INGESTION_AUDIT_COLLECTION,
    LEARNING_ARCHIVE_CHUNKS_COLLECTION,
    LEARNING_ARCHIVE_ITEMS_COLLECTION,
    LEARNING_ARCHIVE_RUNS_COLLECTION,
    NORMALIZATION_FAILURES_COLLECTION,
    REPORT_EXPORTS_COLLECTION,
    REQUIRED_COLLECTIONS,
    RUNTIME_SETTINGS_COLLECTION,
    SCAN_JOBS_COLLECTION,
    SCAN_SESSIONS_COLLECTION,
    VERIFICATION_RUNS_COLLECTION,
)
from app.infrastructure.database.mongo import get_database, get_legacy_database_names


SECURITY_MIGRATION_COLLECTIONS = (
    SCAN_SESSIONS_COLLECTION,
    SCAN_JOBS_COLLECTION,
    FINDINGS_COLLECTION,
    FIX_SUGGESTIONS_COLLECTION,
    VERIFICATION_RUNS_COLLECTION,
    AUDIT_EVENTS_COLLECTION,
    REPORT_EXPORTS_COLLECTION,
)

BUILDER_MIGRATION_COLLECTIONS = (
    BUILDER_WORKSPACES_COLLECTION,
    BUILDER_THREADS_COLLECTION,
    BUILDER_MESSAGES_COLLECTION,
    BUILDER_THREAD_CONTEXTS_COLLECTION,
    BUILDER_MEMORY_ITEMS_COLLECTION,
)


async def ensure_mongo_collections() -> None:
    database = get_database()
    existing = set(await database.list_collection_names())
    for collection_name in REQUIRED_COLLECTIONS:
        if collection_name not in existing:
            await database.create_collection(collection_name)


async def migrate_legacy_collections_if_needed() -> None:
    current_database = get_database()
    for legacy_database_name in get_legacy_database_names():
        legacy_database = get_database(legacy_database_name)
        await _migrate_collection_group_if_needed(
            current_database=current_database,
            legacy_database=legacy_database,
            root_collection=SCAN_SESSIONS_COLLECTION,
            related_collections=SECURITY_MIGRATION_COLLECTIONS,
        )
        await _migrate_collection_group_if_needed(
            current_database=current_database,
            legacy_database=legacy_database,
            root_collection=BUILDER_WORKSPACES_COLLECTION,
            related_collections=BUILDER_MIGRATION_COLLECTIONS,
        )


async def _migrate_collection_group_if_needed(
    *,
    current_database,
    legacy_database,
    root_collection: str,
    related_collections: tuple[str, ...],
) -> None:
    current_root = current_database[root_collection]
    legacy_root = legacy_database[root_collection]
    current_count = await current_root.count_documents({})
    if current_count > 0:
        return

    legacy_count = await legacy_root.count_documents({})
    if legacy_count == 0:
        return

    for collection_name in related_collections:
        current_collection = current_database[collection_name]
        if await current_collection.count_documents({}) > 0:
            continue
        await _copy_collection_documents(
            source_collection=legacy_database[collection_name],
            target_collection=current_collection,
        )


async def _copy_collection_documents(*, source_collection, target_collection, batch_size: int = 250) -> None:
    batch: list[dict] = []
    async for document in source_collection.find({}):
        batch.append(dict(document))
        if len(batch) >= batch_size:
            await target_collection.insert_many(batch, ordered=False)
            batch = []
    if batch:
        await target_collection.insert_many(batch, ordered=False)


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

    learning_archive_runs = database[LEARNING_ARCHIVE_RUNS_COLLECTION]
    await learning_archive_runs.create_index([("run_id", 1)], name="ux_learning_archive_runs_run_id", unique=True)
    await learning_archive_runs.create_index([("created_at", DESCENDING)], name="idx_learning_archive_runs_created_at_desc")
    await learning_archive_runs.create_index([("status", 1), ("created_at", DESCENDING)], name="idx_learning_archive_runs_status_created_at_desc")

    learning_archive_items = database[LEARNING_ARCHIVE_ITEMS_COLLECTION]
    await learning_archive_items.create_index([("item_id", 1)], name="ux_learning_archive_items_item_id", unique=True)
    await learning_archive_items.create_index(
        [("record_type", 1), ("content_fingerprint", 1)],
        name="ux_learning_archive_items_record_fingerprint",
        unique=True,
    )
    await learning_archive_items.create_index([("run_id", 1), ("created_at", DESCENDING)], name="idx_learning_archive_items_run_created_at_desc")
    await learning_archive_items.create_index([("status", 1), ("created_at", DESCENDING)], name="idx_learning_archive_items_status_created_at_desc")
    await learning_archive_items.create_index([("language", 1), ("framework", 1)], name="idx_learning_archive_items_lang_framework")
    await learning_archive_items.create_index([("vulnerability_category", 1)], name="idx_learning_archive_items_vulnerability_category")
    await learning_archive_items.create_index([("repository_fingerprint", 1)], name="idx_learning_archive_items_repository_fingerprint")

    learning_archive_chunks = database[LEARNING_ARCHIVE_CHUNKS_COLLECTION]
    await learning_archive_chunks.create_index([("chunk_id", 1)], name="ux_learning_archive_chunks_chunk_id", unique=True)
    await learning_archive_chunks.create_index(
        [("parent_item_id", 1), ("sequence", 1)],
        name="ux_learning_archive_chunks_parent_sequence",
        unique=True,
    )

    external_sources = database[EXTERNAL_KNOWLEDGE_SOURCES_COLLECTION]
    await external_sources.create_index(
        [("source_name", 1), ("source_version", 1)],
        name="ux_external_knowledge_sources_name_version",
        unique=True,
    )
    await external_sources.create_index([("updated_at", DESCENDING)], name="idx_external_knowledge_sources_updated_at_desc")

    external_items = database[EXTERNAL_KNOWLEDGE_ITEMS_COLLECTION]
    await external_items.create_index([("item_id", 1)], name="ux_external_knowledge_items_item_id", unique=True)
    await external_items.create_index(
        [("source_name", 1), ("source_version", 1), ("item_fingerprint", 1)],
        name="ux_external_knowledge_items_source_fingerprint",
        unique=True,
    )
    await external_items.create_index([("language", 1), ("framework", 1)], name="idx_external_knowledge_items_lang_framework")
    await external_items.create_index([("vulnerability_category", 1)], name="idx_external_knowledge_items_vulnerability_category")
    await external_items.create_index([("weakness_id", 1)], name="idx_external_knowledge_items_weakness_id")
    await external_items.create_index([("source_name", 1), ("created_at", DESCENDING)], name="idx_external_knowledge_items_source_created_at_desc")

    external_chunks = database[EXTERNAL_KNOWLEDGE_CHUNKS_COLLECTION]
    await external_chunks.create_index([("chunk_id", 1)], name="ux_external_knowledge_chunks_chunk_id", unique=True)
    await external_chunks.create_index(
        [("parent_item_id", 1), ("sequence", 1)],
        name="ux_external_knowledge_chunks_parent_sequence",
        unique=True,
    )

    benchmark_suites = database[BENCHMARK_SUITES_COLLECTION]
    await benchmark_suites.create_index([("suite_id", 1)], name="ux_benchmark_suites_suite_id", unique=True)
    await benchmark_suites.create_index([("suite_name", 1)], name="ux_benchmark_suites_suite_name", unique=True)

    benchmark_cases = database[BENCHMARK_CASES_COLLECTION]
    await benchmark_cases.create_index([("case_id", 1)], name="ux_benchmark_cases_case_id", unique=True)
    await benchmark_cases.create_index(
        [("suite_name", 1), ("content_fingerprint", 1)],
        name="ux_benchmark_cases_suite_fingerprint",
        unique=True,
    )
    await benchmark_cases.create_index([("suite_name", 1), ("created_at", DESCENDING)], name="idx_benchmark_cases_suite_created_at_desc")
    await benchmark_cases.create_index([("vulnerability_category", 1)], name="idx_benchmark_cases_vulnerability_category")
    await benchmark_cases.create_index([("language", 1), ("framework", 1)], name="idx_benchmark_cases_lang_framework")

    benchmark_runs = database[BENCHMARK_RUNS_COLLECTION]
    await benchmark_runs.create_index([("run_id", 1)], name="ux_benchmark_runs_run_id", unique=True)
    await benchmark_runs.create_index([("suite_name", 1), ("created_at", DESCENDING)], name="idx_benchmark_runs_suite_created_at_desc")
    await benchmark_runs.create_index([("status", 1), ("created_at", DESCENDING)], name="idx_benchmark_runs_status_created_at_desc")

    feedback_events = database[FEEDBACK_EVENTS_COLLECTION]
    await feedback_events.create_index([("event_id", 1)], name="ux_feedback_events_event_id", unique=True)
    await feedback_events.create_index([("session_id", 1), ("created_at", DESCENDING)], name="idx_feedback_events_session_created_at_desc")
    await feedback_events.create_index([("status", 1), ("created_at", DESCENDING)], name="idx_feedback_events_status_created_at_desc")

    normalization_failures = database[NORMALIZATION_FAILURES_COLLECTION]
    await normalization_failures.create_index([("failure_id", 1)], name="ux_normalization_failures_failure_id", unique=True)
    await normalization_failures.create_index([("run_id", 1), ("created_at", DESCENDING)], name="idx_normalization_failures_run_created_at_desc")
    await normalization_failures.create_index([("source_name", 1), ("created_at", DESCENDING)], name="idx_normalization_failures_source_created_at_desc")

    ingestion_audit = database[INGESTION_AUDIT_COLLECTION]
    await ingestion_audit.create_index([("audit_id", 1)], name="ux_ingestion_audit_audit_id", unique=True)
    await ingestion_audit.create_index([("run_id", 1), ("created_at", DESCENDING)], name="idx_ingestion_audit_run_created_at_desc")
    await ingestion_audit.create_index([("source_name", 1), ("created_at", DESCENDING)], name="idx_ingestion_audit_source_created_at_desc")

    runtime_settings = database[RUNTIME_SETTINGS_COLLECTION]
    await runtime_settings.create_index([("updated_at", DESCENDING)], name="idx_runtime_settings_updated_at_desc")

    builder_workspaces = database[BUILDER_WORKSPACES_COLLECTION]
    await builder_workspaces.create_index([("workspace_id", 1)], name="ux_builder_workspaces_workspace_id", unique=True)
    await builder_workspaces.create_index(
        [("path", 1)],
        name="ux_builder_workspaces_active_path",
        unique=True,
        partialFilterExpression={"archived": False},
    )
    await builder_workspaces.create_index([("updated_at", DESCENDING)], name="idx_builder_workspaces_updated_at_desc")

    builder_threads = database[BUILDER_THREADS_COLLECTION]
    await builder_threads.create_index([("thread_id", 1)], name="ux_builder_threads_thread_id", unique=True)
    await builder_threads.create_index([("workspace_id", 1), ("updated_at", DESCENDING)], name="idx_builder_threads_workspace_updated_at_desc")
    await builder_threads.create_index([("archived", 1), ("updated_at", DESCENDING)], name="idx_builder_threads_archived_updated_at_desc")

    builder_messages = database[BUILDER_MESSAGES_COLLECTION]
    await builder_messages.create_index([("message_id", 1)], name="ux_builder_messages_message_id", unique=True)
    await builder_messages.create_index([("thread_id", 1), ("created_at", 1)], name="idx_builder_messages_thread_created_at_asc")
    await builder_messages.create_index([("workspace_id", 1), ("created_at", DESCENDING)], name="idx_builder_messages_workspace_created_at_desc")

    builder_thread_contexts = database[BUILDER_THREAD_CONTEXTS_COLLECTION]
    await builder_thread_contexts.create_index([("thread_id", 1)], name="ux_builder_thread_contexts_thread_id", unique=True)
    await builder_thread_contexts.create_index(
        [("workspace_id", 1), ("updated_at", DESCENDING)],
        name="idx_builder_thread_contexts_workspace_updated_at_desc",
    )

    builder_memory_items = database[BUILDER_MEMORY_ITEMS_COLLECTION]
    await builder_memory_items.create_index([("memory_id", 1)], name="ux_builder_memory_items_memory_id", unique=True)
    await builder_memory_items.create_index(
        [("workspace_id", 1), ("content_fingerprint", 1)],
        name="ux_builder_memory_items_workspace_fingerprint",
        unique=True,
    )
    await builder_memory_items.create_index(
        [("thread_id", 1), ("updated_at", DESCENDING)],
        name="idx_builder_memory_items_thread_updated_at_desc",
    )
    await builder_memory_items.create_index(
        [("workspace_id", 1), ("memory_class", 1), ("updated_at", DESCENDING)],
        name="idx_builder_memory_items_workspace_class_updated_at_desc",
    )


def ensure_artifacts_directory() -> Path:
    artifacts_dir = Path(get_settings().artifacts_dir).expanduser().resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


async def ensure_backend_bootstrap() -> None:
    await ensure_mongo_collections()
    await migrate_legacy_collections_if_needed()
    await ensure_mongo_indexes()
    ensure_artifacts_directory()
