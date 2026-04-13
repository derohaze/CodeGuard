import asyncio
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database.collections import (
    BENCHMARK_CASES_COLLECTION,
    BENCHMARK_RUNS_COLLECTION,
    BENCHMARK_SUITES_COLLECTION,
    EXTERNAL_KNOWLEDGE_CHUNKS_COLLECTION,
    EXTERNAL_KNOWLEDGE_ITEMS_COLLECTION,
    EXTERNAL_KNOWLEDGE_SOURCES_COLLECTION,
    FEEDBACK_EVENTS_COLLECTION,
    INGESTION_AUDIT_COLLECTION,
    LEARNING_ARCHIVE_CHUNKS_COLLECTION,
    LEARNING_ARCHIVE_ITEMS_COLLECTION,
    LEARNING_ARCHIVE_RUNS_COLLECTION,
    NORMALIZATION_FAILURES_COLLECTION,
)
from app.infrastructure.learning.repository import LearningArchiveMongoRepository


def _build_database_mock() -> dict:
    collections = {}
    for name in (
        LEARNING_ARCHIVE_RUNS_COLLECTION,
        LEARNING_ARCHIVE_ITEMS_COLLECTION,
        LEARNING_ARCHIVE_CHUNKS_COLLECTION,
        EXTERNAL_KNOWLEDGE_SOURCES_COLLECTION,
        EXTERNAL_KNOWLEDGE_ITEMS_COLLECTION,
        EXTERNAL_KNOWLEDGE_CHUNKS_COLLECTION,
        BENCHMARK_SUITES_COLLECTION,
        BENCHMARK_CASES_COLLECTION,
        BENCHMARK_RUNS_COLLECTION,
        FEEDBACK_EVENTS_COLLECTION,
        NORMALIZATION_FAILURES_COLLECTION,
        INGESTION_AUDIT_COLLECTION,
    ):
        collection = MagicMock()
        collection.update_one = AsyncMock()
        collection.find_one = AsyncMock(return_value=None)
        collections[name] = collection
    return collections


class LearningRepositoryTests(unittest.TestCase):
    def test_upsert_benchmark_case_does_not_duplicate_case_id_in_update_document(self):
        database = _build_database_mock()
        with patch("app.infrastructure.learning.repository.get_database", return_value=database):
            repository = LearningArchiveMongoRepository()
            asyncio.run(
                repository.upsert_benchmark_case(
                    {
                        "case_id": "case_123",
                        "suite_name": "detection",
                        "source_system": "juliet_seed",
                        "content_fingerprint": "fp_1",
                    }
                )
            )

        update_doc = database[BENCHMARK_CASES_COLLECTION].update_one.call_args.args[1]
        self.assertNotIn("case_id", update_doc["$set"])
        self.assertNotIn("created_at", update_doc["$set"])

    def test_record_feedback_event_does_not_duplicate_event_fields_in_update_document(self):
        database = _build_database_mock()
        with patch("app.infrastructure.learning.repository.get_database", return_value=database):
            repository = LearningArchiveMongoRepository()
            asyncio.run(
                repository.record_feedback_event(
                    {
                        "event_id": "evt_1",
                        "created_at": datetime.now(timezone.utc),
                        "status": "candidate",
                    }
                )
            )

        update_doc = database[FEEDBACK_EVENTS_COLLECTION].update_one.call_args.args[1]
        self.assertNotIn("event_id", update_doc["$set"])
        self.assertNotIn("created_at", update_doc["$set"])


if __name__ == "__main__":
    unittest.main()
