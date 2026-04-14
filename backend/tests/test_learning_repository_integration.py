import asyncio
import sys
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from pymongo import AsyncMongoClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.infrastructure.learning.repository import LearningArchiveMongoRepository


class LearningRepositoryIntegrationTests(unittest.TestCase):
    def test_repository_persistence_and_dedup_end_to_end(self):
        settings = get_settings()
        asyncio.run(self._run_case(settings.mongodb_uri))

    async def _run_case(self, mongodb_uri: str) -> None:
        db_name = f"khwarizm_learning_it_{uuid4().hex[:10]}"
        client = AsyncMongoClient(
            mongodb_uri,
            serverSelectionTimeoutMS=3000,
            uuidRepresentation="standard",
        )
        database = client[db_name]
        connected = False
        try:
            try:
                await database.command("ping")
                connected = True
            except Exception as exc:
                raise unittest.SkipTest(f"Mongo integration test skipped: {exc}") from exc

            with patch("app.infrastructure.learning.repository.get_database", return_value=database):
                repository = LearningArchiveMongoRepository()

                item = {
                    "schema_version": "1.0.0",
                    "record_type": "security_pattern",
                    "source_name": "cwe",
                    "source_version": "4.14",
                    "item_type": "security_pattern",
                    "language": "python",
                    "framework": "fastapi",
                    "vulnerability_category": "sql_injection",
                    "weakness_id": "CWE-89",
                    "title": "SQL Injection",
                    "summary": "unsafe query",
                    "tags": ["sql", "injection"],
                    "content_fingerprint": "fp_ext_1",
                    "raw_reference": {"ingestion_run_id": "run_1"},
                }
                item_id, inserted = await repository.upsert_external_item(
                    ingestion_run_id="run_1",
                    item=item,
                    large_body="A" * 20_000,
                    body_type="prose",
                )
                self.assertTrue(inserted)
                self.assertTrue(item_id)

                same_item_id, inserted_again = await repository.upsert_external_item(
                    ingestion_run_id="run_2",
                    item=item,
                    large_body="A" * 20_000,
                    body_type="prose",
                )
                self.assertFalse(inserted_again)
                self.assertEqual(item_id, same_item_id)

                chunks = await repository.get_external_chunks(parent_item_id=item_id)
                self.assertGreater(len(chunks), 1)

                case = {
                    "case_id": "case_custom_1",
                    "suite_name": "detection",
                    "source_system": "juliet_seed",
                    "vulnerability_category": "sql_injection",
                    "content_fingerprint": "bench_fp_1",
                }
                case_id = await repository.upsert_benchmark_case(case)
                self.assertTrue(case_id)
                same_case_id = await repository.upsert_benchmark_case(
                    {
                        **case,
                        "case_id": "case_custom_2",
                    }
                )
                self.assertEqual(case_id, same_case_id)
        finally:
            if connected:
                await client.drop_database(db_name)
            await client.close()


if __name__ == "__main__":
    unittest.main()
