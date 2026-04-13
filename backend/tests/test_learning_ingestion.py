import asyncio
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.learning.external_parsers import parse_external_payload_with_parser
from app.infrastructure.learning.ingestion import ExternalKnowledgeIngestionService, parse_external_payload
from app.infrastructure.learning.schemas import ExternalKnowledgeSourceSpec


class StaticFetcher:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls = 0

    async def fetch(self, endpoint: str) -> str:
        self.calls += 1
        return self.payload


class InMemoryLearningRepository:
    def __init__(self) -> None:
        self.sources = set()
        self.items = {}
        self.audits = []
        self.failures = []

    async def upsert_external_source(self, source: dict) -> str:
        key = (source["source_name"], source["source_version"])
        self.sources.add(key)
        return f"src_{source['source_name']}"

    async def cache_external_raw_payload(self, *, ingestion_run_id: str, source_name: str, source_version: str, payload_text: str) -> str:
        return f"raw_{source_name}_{source_version}"

    async def upsert_external_item(self, *, ingestion_run_id: str, item: dict, large_body: str | None = None, body_type: str = "prose") -> tuple[str, bool]:
        key = (item.get("source_name"), item.get("source_version"), item["content_fingerprint"])
        if key in self.items:
            return self.items[key], False
        item_id = f"item_{len(self.items) + 1}"
        self.items[key] = item_id
        return item_id, True

    async def record_normalization_failure(self, *, run_id: str, source_name: str, item_ref: str, error_message: str, payload_excerpt: str | None) -> str:
        self.failures.append((run_id, source_name, item_ref))
        return "failure_1"

    async def create_ingestion_audit(self, *, run_id: str, source_name: str, status: str, details: dict) -> str:
        self.audits.append((run_id, source_name, status, details))
        return f"audit_{len(self.audits)}"


class LearningIngestionTests(unittest.TestCase):
    def test_parse_external_payload_supports_json_items(self):
        payload = '{"items":[{"title":"One"},{"title":"Two"}]}'
        parsed = parse_external_payload(payload)
        self.assertEqual(len(parsed), 2)

    def test_parse_external_payload_uses_cwe_parser_when_source_is_cwe(self):
        payload = '{"Weaknesses":{"Weakness":[{"ID":"89","Name":"SQL Injection","Description":"Unsafe query"}]}}'
        parsed = parse_external_payload_with_parser(payload, source_name="cwe")
        self.assertEqual(parsed.parser_name, "cwe_parser")
        self.assertEqual(parsed.items[0]["weakness_id"], "CWE-89")

    def test_ingestion_is_idempotent_on_reingestion(self):
        repository = InMemoryLearningRepository()
        fetcher = StaticFetcher('[{"title":"SQL Injection","summary":"desc","item_type":"security_pattern"}]')
        service = ExternalKnowledgeIngestionService(repository=repository, fetcher=fetcher)
        source = ExternalKnowledgeSourceSpec(
            source_name="cwe",
            source_version="4.14",
            endpoint="https://example.test/cwe.json",
            item_type="security_pattern",
        )

        first = asyncio.run(service.ingest([source]))
        second = asyncio.run(service.ingest([source]))

        self.assertEqual(first.item_written, 1)
        self.assertEqual(second.item_skipped, 1)
        self.assertGreaterEqual(fetcher.calls, 2)
        self.assertEqual(repository.audits[0][2], "completed")
        self.assertIn("parser_name", repository.audits[0][3])


if __name__ == "__main__":
    unittest.main()
