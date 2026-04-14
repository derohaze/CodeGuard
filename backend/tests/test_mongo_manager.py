import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database.mongo_manager import ensure_backend_bootstrap, ensure_mongo_indexes, migrate_legacy_collections_if_needed


class MongoManagerTests(unittest.TestCase):
    def test_ensure_indexes_creates_expected_scan_session_indexes(self):
        scan_sessions = MagicMock()
        scan_sessions.create_index = AsyncMock()
        scan_jobs = MagicMock()
        scan_jobs.create_index = AsyncMock()
        findings = MagicMock()
        findings.create_index = AsyncMock()
        findings.update_many = AsyncMock()
        findings.index_information = AsyncMock(return_value={"ux_findings_finding_id": {}})
        findings.drop_index = AsyncMock()
        fix_suggestions = MagicMock()
        fix_suggestions.create_index = AsyncMock()
        verification_runs = MagicMock()
        verification_runs.create_index = AsyncMock()
        audit_events = MagicMock()
        audit_events.create_index = AsyncMock()
        report_exports = MagicMock()
        report_exports.create_index = AsyncMock()
        learning_archive_runs = MagicMock()
        learning_archive_runs.create_index = AsyncMock()
        learning_archive_items = MagicMock()
        learning_archive_items.create_index = AsyncMock()
        learning_archive_chunks = MagicMock()
        learning_archive_chunks.create_index = AsyncMock()
        external_knowledge_sources = MagicMock()
        external_knowledge_sources.create_index = AsyncMock()
        external_knowledge_items = MagicMock()
        external_knowledge_items.create_index = AsyncMock()
        external_knowledge_chunks = MagicMock()
        external_knowledge_chunks.create_index = AsyncMock()
        benchmark_suites = MagicMock()
        benchmark_suites.create_index = AsyncMock()
        benchmark_cases = MagicMock()
        benchmark_cases.create_index = AsyncMock()
        benchmark_runs = MagicMock()
        benchmark_runs.create_index = AsyncMock()
        feedback_events = MagicMock()
        feedback_events.create_index = AsyncMock()
        normalization_failures = MagicMock()
        normalization_failures.create_index = AsyncMock()
        ingestion_audit = MagicMock()
        ingestion_audit.create_index = AsyncMock()
        runtime_settings = MagicMock()
        runtime_settings.create_index = AsyncMock()
        builder_workspaces = MagicMock()
        builder_workspaces.create_index = AsyncMock()
        builder_threads = MagicMock()
        builder_threads.create_index = AsyncMock()
        builder_messages = MagicMock()
        builder_messages.create_index = AsyncMock()
        builder_thread_contexts = MagicMock()
        builder_thread_contexts.create_index = AsyncMock()
        builder_memory_items = MagicMock()
        builder_memory_items.create_index = AsyncMock()
        database = {
            "scan_sessions": scan_sessions,
            "scan_jobs": scan_jobs,
            "findings": findings,
            "fix_suggestions": fix_suggestions,
            "verification_runs": verification_runs,
            "audit_events": audit_events,
            "report_exports": report_exports,
            "learning_archive_runs": learning_archive_runs,
            "learning_archive_items": learning_archive_items,
            "learning_archive_chunks": learning_archive_chunks,
            "external_knowledge_sources": external_knowledge_sources,
            "external_knowledge_items": external_knowledge_items,
            "external_knowledge_chunks": external_knowledge_chunks,
            "benchmark_suites": benchmark_suites,
            "benchmark_cases": benchmark_cases,
            "benchmark_runs": benchmark_runs,
            "feedback_events": feedback_events,
            "normalization_failures": normalization_failures,
            "ingestion_audit": ingestion_audit,
            "runtime_settings": runtime_settings,
            "builder_workspaces": builder_workspaces,
            "builder_threads": builder_threads,
            "builder_messages": builder_messages,
            "builder_thread_contexts": builder_thread_contexts,
            "builder_memory_items": builder_memory_items,
        }
        with patch("app.infrastructure.database.mongo_manager.get_database", return_value=database):
            asyncio.run(ensure_mongo_indexes())

        created_names = [call.kwargs.get("name") for call in scan_sessions.create_index.call_args_list]
        self.assertIn("idx_scan_sessions_updated_at_desc", created_names)
        self.assertIn("idx_scan_sessions_status_updated_at_desc", created_names)
        self.assertIn("idx_scan_sessions_repo_updated_at_desc", created_names)
        self.assertIn("ux_scan_sessions_session_id", created_names)

        scan_job_index_names = [call.kwargs.get("name") for call in scan_jobs.create_index.call_args_list]
        self.assertIn("ux_scan_jobs_job_id", scan_job_index_names)
        self.assertIn("idx_scan_jobs_session_created_at_desc", scan_job_index_names)
        self.assertIn("idx_scan_jobs_status_created_at_desc", scan_job_index_names)
        self.assertIn("idx_scan_jobs_source_status_created_at_desc", scan_job_index_names)
        finding_index_names = [call.kwargs.get("name") for call in findings.create_index.call_args_list]
        self.assertIn("ux_findings_session_kind_finding_id", finding_index_names)
        benchmark_case_index_names = [call.kwargs.get("name") for call in benchmark_cases.create_index.call_args_list]
        self.assertIn("ux_benchmark_cases_suite_fingerprint", benchmark_case_index_names)
        builder_workspace_index_names = [call.kwargs.get("name") for call in builder_workspaces.create_index.call_args_list]
        self.assertIn("ux_builder_workspaces_workspace_id", builder_workspace_index_names)
        self.assertIn("ux_builder_workspaces_active_path", builder_workspace_index_names)
        builder_context_index_names = [call.kwargs.get("name") for call in builder_thread_contexts.create_index.call_args_list]
        self.assertIn("ux_builder_thread_contexts_thread_id", builder_context_index_names)
        builder_memory_index_names = [call.kwargs.get("name") for call in builder_memory_items.create_index.call_args_list]
        self.assertIn("ux_builder_memory_items_workspace_fingerprint", builder_memory_index_names)

    def test_backend_bootstrap_creates_missing_collections(self):
        database = MagicMock()
        database.list_collection_names = AsyncMock(return_value=["scan_sessions"])
        database.create_collection = AsyncMock()
        collections = {}
        for name in (
            "scan_sessions",
            "scan_jobs",
            "findings",
            "fix_suggestions",
            "verification_runs",
            "audit_events",
            "report_exports",
            "learning_archive_runs",
            "learning_archive_items",
            "learning_archive_chunks",
            "external_knowledge_sources",
            "external_knowledge_items",
            "external_knowledge_chunks",
            "benchmark_suites",
            "benchmark_cases",
            "benchmark_runs",
            "feedback_events",
            "normalization_failures",
            "ingestion_audit",
            "runtime_settings",
            "builder_workspaces",
            "builder_threads",
            "builder_messages",
            "builder_thread_contexts",
            "builder_memory_items",
        ):
            collection = MagicMock()
            collection.create_index = AsyncMock()
            collection.update_many = AsyncMock()
            collection.index_information = AsyncMock(return_value={})
            collection.drop_index = AsyncMock()
            collections[name] = collection
        database.__getitem__.side_effect = collections.__getitem__
        with patch("app.infrastructure.database.mongo_manager.get_database", return_value=database), patch(
            "app.infrastructure.database.mongo_manager.get_legacy_database_names",
            return_value=[],
        ), patch(
            "app.infrastructure.database.mongo_manager.ensure_artifacts_directory"
        ):
            asyncio.run(ensure_backend_bootstrap())

        created = [call.args[0] for call in database.create_collection.call_args_list]
        self.assertIn("scan_jobs", created)
        self.assertIn("audit_events", created)

    def test_migrate_legacy_collections_copies_security_and_builder_data_when_current_is_empty(self):
        copied_collection_names: list[str] = []

        current_scan_sessions = MagicMock()
        current_scan_sessions.count_documents = AsyncMock(return_value=0)
        current_scan_sessions.insert_many = AsyncMock(side_effect=lambda docs, ordered=False: copied_collection_names.append("scan_sessions"))
        current_builder_workspaces = MagicMock()
        current_builder_workspaces.count_documents = AsyncMock(return_value=0)
        current_builder_workspaces.insert_many = AsyncMock(side_effect=lambda docs, ordered=False: copied_collection_names.append("builder_workspaces"))

        def current_collection(name: str):
            collection = MagicMock()
            if name == "scan_sessions":
                return current_scan_sessions
            if name == "builder_workspaces":
                return current_builder_workspaces
            collection.count_documents = AsyncMock(return_value=0)
            collection.insert_many = AsyncMock(side_effect=lambda docs, ordered=False, _name=name: copied_collection_names.append(_name))
            return collection

        legacy_scan_sessions = MagicMock()
        legacy_scan_sessions.count_documents = AsyncMock(return_value=2)
        legacy_scan_sessions.find.return_value = _AsyncCursor([{"_id": "s1"}, {"_id": "s2"}])
        legacy_builder_workspaces = MagicMock()
        legacy_builder_workspaces.count_documents = AsyncMock(return_value=1)
        legacy_builder_workspaces.find.return_value = _AsyncCursor([{"_id": "w1"}])

        def legacy_collection(name: str):
            collection = MagicMock()
            if name == "scan_sessions":
                return legacy_scan_sessions
            if name == "builder_workspaces":
                return legacy_builder_workspaces
            collection.find.return_value = _AsyncCursor([{"_id": f"{name}-1"}])
            return collection

        current_database = MagicMock()
        current_database.__getitem__.side_effect = current_collection
        legacy_database = MagicMock()
        legacy_database.__getitem__.side_effect = legacy_collection

        def get_database(database_name=None):
            return legacy_database if database_name == "CodeGuard" else current_database

        with patch("app.infrastructure.database.mongo_manager.get_database", side_effect=get_database), patch(
            "app.infrastructure.database.mongo_manager.get_legacy_database_names",
            return_value=["CodeGuard"],
        ):
            asyncio.run(migrate_legacy_collections_if_needed())

        self.assertIn("scan_jobs", copied_collection_names)
        self.assertIn("findings", copied_collection_names)
        self.assertIn("builder_threads", copied_collection_names)
        self.assertIn("builder_messages", copied_collection_names)


class _AsyncCursor:
    def __init__(self, items):
        self._items = items
        self._index = 0

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item


if __name__ == "__main__":
    unittest.main()
