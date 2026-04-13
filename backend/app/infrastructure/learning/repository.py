from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pymongo import DESCENDING

from app.core.config import get_settings
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
from app.infrastructure.database.mongo import get_database
from app.infrastructure.learning.chunking import ChunkPolicy, build_chunk_documents
from app.infrastructure.learning.fingerprints import bounded_identifier


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LearningArchiveMongoRepository:
    def __init__(self) -> None:
        database = get_database()
        self.learning_archive_runs = database[LEARNING_ARCHIVE_RUNS_COLLECTION]
        self.learning_archive_items = database[LEARNING_ARCHIVE_ITEMS_COLLECTION]
        self.learning_archive_chunks = database[LEARNING_ARCHIVE_CHUNKS_COLLECTION]
        self.external_knowledge_sources = database[EXTERNAL_KNOWLEDGE_SOURCES_COLLECTION]
        self.external_knowledge_items = database[EXTERNAL_KNOWLEDGE_ITEMS_COLLECTION]
        self.external_knowledge_chunks = database[EXTERNAL_KNOWLEDGE_CHUNKS_COLLECTION]
        self.benchmark_suites = database[BENCHMARK_SUITES_COLLECTION]
        self.benchmark_cases = database[BENCHMARK_CASES_COLLECTION]
        self.benchmark_runs = database[BENCHMARK_RUNS_COLLECTION]
        self.feedback_events = database[FEEDBACK_EVENTS_COLLECTION]
        self.normalization_failures = database[NORMALIZATION_FAILURES_COLLECTION]
        self.ingestion_audit = database[INGESTION_AUDIT_COLLECTION]
        settings = get_settings()
        self.chunk_policy = ChunkPolicy(
            chunk_size_chars=max(1024, int(settings.learning_chunk_size_chars)),
            prose_overlap_chars=max(0, int(settings.learning_prose_chunk_overlap_chars)),
        )

    async def create_archive_run(self, *, trigger: str, source_system: str, metadata: dict | None = None) -> str:
        run_id = bounded_identifier("archive_run", f"{uuid4()}:{trigger}:{source_system}")
        now = utc_now()
        await self.learning_archive_runs.insert_one(
            {
                "_id": run_id,
                "run_id": run_id,
                "trigger": trigger,
                "source_system": source_system,
                "status": "running",
                "metadata": metadata or {},
                "metrics": {"items_written": 0, "items_skipped": 0, "failures": 0},
                "created_at": now,
                "updated_at": now,
                "completed_at": None,
            }
        )
        return run_id

    async def finalize_archive_run(self, run_id: str, *, status: str, metrics: dict) -> None:
        now = utc_now()
        await self.learning_archive_runs.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "status": status,
                    "metrics": metrics,
                    "updated_at": now,
                    "completed_at": now,
                }
            },
        )

    async def upsert_learning_archive_item(self, *, run_id: str, item: dict, large_body: str | None = None, body_type: str = "prose") -> tuple[str, bool]:
        content_fingerprint = str(item["content_fingerprint"])
        filter_doc = {
            "record_type": item["record_type"],
            "content_fingerprint": content_fingerprint,
        }
        existing = await self.learning_archive_items.find_one(filter_doc, {"_id": 1})
        if existing is not None:
            await self.learning_archive_items.update_one(filter_doc, {"$set": {"updated_at": utc_now(), "last_run_id": run_id}})
            return str(existing["_id"]), False

        item_id = str(item.get("record_id") or bounded_identifier("learn_item", content_fingerprint))
        now = utc_now()
        item_document = {
            "_id": item_id,
            "item_id": item_id,
            "run_id": run_id,
            "last_run_id": run_id,
            "schema_version": item.get("schema_version"),
            "record_type": item["record_type"],
            "source_system": item.get("source_system"),
            "status": item.get("status"),
            "language": item.get("language"),
            "framework": item.get("framework"),
            "repository_fingerprint": item.get("repository_fingerprint"),
            "vulnerability_category": item.get("vulnerability_category"),
            "severity": item.get("severity"),
            "confidence": item.get("confidence"),
            "tags": item.get("tags", []),
            "raw_reference": item.get("raw_reference", {}),
            "content_fingerprint": content_fingerprint,
            "body_chunk_ref": None,
            "body_chunk_count": 0,
            "body_checksum": None,
            "created_at": now,
            "updated_at": now,
            "payload": {
                # keep payload metadata compact in parent document
                "file_paths": item.get("file_paths", []),
                "human_outcome": item.get("human_outcome", {}),
                "verification_outcome": item.get("verification_outcome", {}),
            },
        }

        body_content = large_body or ""
        if body_content:
            chunk_documents, chunk_metadata = build_chunk_documents(
                parent_item_id=item_id,
                content=body_content,
                content_type=body_type,
                policy=self.chunk_policy,
            )
            if chunk_documents:
                await self.learning_archive_chunks.insert_many(chunk_documents, ordered=False)
                item_document["body_chunk_ref"] = item_id
                item_document["body_chunk_count"] = chunk_metadata["chunk_count"]
                item_document["body_checksum"] = chunk_metadata["parent_checksum"]
                item_document["chunk_policy"] = chunk_metadata

        await self.learning_archive_items.insert_one(item_document)
        return item_id, True

    async def create_ingestion_audit(self, *, run_id: str, source_name: str, status: str, details: dict) -> str:
        audit_id = bounded_identifier("ingest_audit", f"{run_id}:{source_name}:{uuid4()}")
        now = utc_now()
        await self.ingestion_audit.insert_one(
            {
                "_id": audit_id,
                "audit_id": audit_id,
                "run_id": run_id,
                "source_name": source_name,
                "status": status,
                "details": details,
                "created_at": now,
                "updated_at": now,
            }
        )
        return audit_id

    async def record_normalization_failure(
        self,
        *,
        run_id: str,
        source_name: str,
        item_ref: str,
        error_message: str,
        payload_excerpt: str | None,
    ) -> str:
        failure_id = bounded_identifier("norm_fail", f"{run_id}:{source_name}:{item_ref}:{uuid4()}")
        now = utc_now()
        await self.normalization_failures.insert_one(
            {
                "_id": failure_id,
                "failure_id": failure_id,
                "run_id": run_id,
                "source_name": source_name,
                "item_ref": item_ref,
                "error_message": error_message,
                "payload_excerpt": payload_excerpt or "",
                "created_at": now,
            }
        )
        return failure_id

    async def upsert_external_source(self, source: dict) -> str:
        source_name = str(source["source_name"]).strip().lower()
        source_version = str(source["source_version"]).strip().lower()
        source_id = bounded_identifier("ext_source", f"{source_name}:{source_version}")
        now = utc_now()
        await self.external_knowledge_sources.update_one(
            {"_id": source_id},
            {
                "$setOnInsert": {
                    "_id": source_id,
                    "source_id": source_id,
                    "source_name": source_name,
                    "source_version": source_version,
                    "created_at": now,
                },
                "$set": {
                    "endpoint": source.get("endpoint"),
                    "license_notes": source.get("license_notes"),
                    "original_reference": source.get("original_reference"),
                    "updated_at": now,
                },
            },
            upsert=True,
        )
        return source_id

    async def upsert_external_item(self, *, ingestion_run_id: str, item: dict, large_body: str | None = None, body_type: str = "prose") -> tuple[str, bool]:
        item_fingerprint = str(item["content_fingerprint"])
        source_name = str(item.get("source_name", "")).strip().lower()
        source_version = str(item.get("source_version", "")).strip().lower()
        filter_doc = {
            "source_name": source_name,
            "source_version": source_version,
            "item_fingerprint": item_fingerprint,
        }
        existing = await self.external_knowledge_items.find_one(filter_doc, {"_id": 1})
        if existing is not None:
            await self.external_knowledge_items.update_one(
                {"_id": existing["_id"]},
                {"$set": {"updated_at": utc_now(), "last_ingestion_run_id": ingestion_run_id}},
            )
            return str(existing["_id"]), False

        item_id = str(item.get("pattern_id") or item.get("rule_id") or bounded_identifier("ext_item", item_fingerprint))
        now = utc_now()
        document = {
            "_id": item_id,
            "item_id": item_id,
            "ingestion_run_id": ingestion_run_id,
            "last_ingestion_run_id": ingestion_run_id,
            "schema_version": item.get("schema_version"),
            "record_type": item.get("record_type"),
            "source_name": source_name,
            "source_version": source_version,
            "item_type": item.get("item_type"),
            "language": item.get("language"),
            "framework": item.get("framework"),
            "vulnerability_category": item.get("vulnerability_category"),
            "weakness_id": item.get("weakness_id"),
            "title": item.get("title"),
            "summary": item.get("summary"),
            "tags": item.get("tags", []),
            "license_notes": item.get("license_notes"),
            "original_reference": item.get("original_reference"),
            "item_fingerprint": item_fingerprint,
            "raw_reference": item.get("raw_reference", {}),
            "body_chunk_ref": None,
            "body_chunk_count": 0,
            "body_checksum": None,
            "created_at": now,
            "updated_at": now,
            "retrieval_text": " ".join(
                part
                for part in [
                    str(item.get("title") or ""),
                    str(item.get("summary") or ""),
                    str(item.get("vulnerability_category") or ""),
                    str(item.get("weakness_id") or ""),
                    " ".join(item.get("tags") or []),
                ]
                if part
            ).lower(),
        }
        raw_content = large_body or _derive_external_body(item)
        if raw_content:
            chunk_documents, chunk_metadata = build_chunk_documents(
                parent_item_id=item_id,
                content=raw_content,
                content_type=body_type,
                policy=self.chunk_policy,
            )
            if chunk_documents:
                await self.external_knowledge_chunks.insert_many(chunk_documents, ordered=False)
                document["body_chunk_ref"] = item_id
                document["body_chunk_count"] = chunk_metadata["chunk_count"]
                document["body_checksum"] = chunk_metadata["parent_checksum"]
                document["chunk_policy"] = chunk_metadata
        await self.external_knowledge_items.insert_one(document)
        return item_id, True

    async def cache_external_raw_payload(
        self,
        *,
        ingestion_run_id: str,
        source_name: str,
        source_version: str,
        payload_text: str,
    ) -> str:
        cache_item_id = bounded_identifier("ext_raw", f"{source_name}:{source_version}:{payload_text[:256]}")
        existing = await self.external_knowledge_items.find_one({"_id": cache_item_id}, {"_id": 1})
        if existing is not None:
            return cache_item_id

        now = utc_now()
        chunk_documents, chunk_metadata = build_chunk_documents(
            parent_item_id=cache_item_id,
            content=payload_text,
            content_type="prose",
            policy=self.chunk_policy,
        )
        if chunk_documents:
            await self.external_knowledge_chunks.insert_many(chunk_documents, ordered=False)
        await self.external_knowledge_items.insert_one(
            {
                "_id": cache_item_id,
                "item_id": cache_item_id,
                "ingestion_run_id": ingestion_run_id,
                "last_ingestion_run_id": ingestion_run_id,
                "record_type": "raw_payload",
                "source_name": source_name.strip().lower(),
                "source_version": source_version.strip().lower(),
                "item_type": "raw_payload",
                "title": f"Raw payload cache for {source_name}",
                "summary": "Cached raw source response before parsing.",
                "tags": ["raw_payload", "ingestion_cache"],
                "item_fingerprint": bounded_identifier("raw_fp", payload_text, length=32),
                "raw_reference": {"ingestion_run_id": ingestion_run_id},
                "body_chunk_ref": cache_item_id,
                "body_chunk_count": chunk_metadata["chunk_count"],
                "body_checksum": chunk_metadata["parent_checksum"],
                "chunk_policy": chunk_metadata,
                "retrieval_text": "",
                "created_at": now,
                "updated_at": now,
            }
        )
        return cache_item_id

    async def record_feedback_event(self, event: dict) -> str:
        event_id = str(event.get("event_id") or bounded_identifier("feedback_evt", f"{uuid4()}"))
        now = utc_now()
        event_updates = dict(event)
        event_updates.pop("event_id", None)
        event_updates.pop("created_at", None)
        await self.feedback_events.update_one(
            {"_id": event_id},
            {
                "$setOnInsert": {"_id": event_id, "event_id": event_id, "created_at": now},
                "$set": {**event_updates, "updated_at": now},
            },
            upsert=True,
        )
        return event_id

    async def upsert_benchmark_suite(self, suite_name: str, *, metadata: dict | None = None) -> str:
        suite_id = bounded_identifier("bench_suite", suite_name.lower())
        now = utc_now()
        await self.benchmark_suites.update_one(
            {"_id": suite_id},
            {
                "$setOnInsert": {"_id": suite_id, "suite_id": suite_id, "suite_name": suite_name, "created_at": now},
                "$set": {"metadata": metadata or {}, "updated_at": now},
            },
            upsert=True,
        )
        return suite_id

    async def upsert_benchmark_case(self, case: dict) -> str:
        content_fingerprint = case.get("content_fingerprint")
        existing_case = None
        if content_fingerprint:
            existing_case = await self.benchmark_cases.find_one(
                {
                    "suite_name": case.get("suite_name"),
                    "content_fingerprint": content_fingerprint,
                },
                {"_id": 1},
            )
        case_id = str(
            case.get("case_id")
            or (existing_case.get("_id") if existing_case else None)
            or bounded_identifier("bench_case", content_fingerprint or case)
        )
        now = utc_now()
        case_updates = dict(case)
        case_updates.pop("case_id", None)
        case_updates.pop("created_at", None)
        await self.benchmark_cases.update_one(
            {"_id": case_id},
            {"$setOnInsert": {"_id": case_id, "case_id": case_id, "created_at": now}, "$set": {**case_updates, "updated_at": now}},
            upsert=True,
        )
        return case_id

    async def create_benchmark_run(self, *, suite_name: str, benchmark_type: str, metadata: dict | None = None) -> str:
        run_id = bounded_identifier("bench_run", f"{suite_name}:{benchmark_type}:{uuid4()}")
        now = utc_now()
        await self.benchmark_runs.insert_one(
            {
                "_id": run_id,
                "run_id": run_id,
                "suite_name": suite_name,
                "benchmark_type": benchmark_type,
                "status": "running",
                "metadata": metadata or {},
                "metrics": {},
                "created_at": now,
                "updated_at": now,
                "completed_at": None,
            }
        )
        return run_id

    async def finalize_benchmark_run(self, run_id: str, *, status: str, metrics: dict, artifacts: dict | None = None) -> None:
        now = utc_now()
        await self.benchmark_runs.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "status": status,
                    "metrics": metrics,
                    "artifacts": artifacts or {},
                    "updated_at": now,
                    "completed_at": now,
                }
            },
        )

    async def list_archive_items(self, *, statuses: list[str] | None = None, limit: int = 250) -> list[dict]:
        query: dict[str, Any] = {}
        if statuses:
            query["status"] = {"$in": statuses}
        cursor = self.learning_archive_items.find(query).sort("created_at", DESCENDING).limit(limit)
        return [item async for item in cursor]

    async def list_benchmark_cases(self, *, suite_name: str, limit: int = 500) -> list[dict]:
        cursor = self.benchmark_cases.find({"suite_name": suite_name}).sort("created_at", DESCENDING).limit(limit)
        return [item async for item in cursor]

    async def list_recent_ingestion_audits(self, *, limit: int = 200) -> list[dict]:
        cursor = self.ingestion_audit.find({}).sort("created_at", DESCENDING).limit(limit)
        return [item async for item in cursor]

    async def count_normalization_failures(self, *, run_id: str | None = None) -> int:
        query: dict[str, Any] = {}
        if run_id:
            query["run_id"] = run_id
        return int(await self.normalization_failures.count_documents(query))

    async def search_external_knowledge(
        self,
        *,
        query_text: str,
        source_name: str | None,
        language: str | None,
        framework: str | None,
        vulnerability_category: str | None,
        weakness_id: str | None,
        tags: list[str] | None,
        limit: int,
        offset: int,
    ) -> list[dict]:
        query: dict[str, Any] = {}
        if source_name:
            query["source_name"] = source_name.strip().lower()
        if language:
            query["language"] = language.strip().lower()
        if framework:
            query["framework"] = framework.strip().lower()
        if vulnerability_category:
            query["vulnerability_category"] = vulnerability_category.strip().lower()
        if weakness_id:
            query["weakness_id"] = weakness_id.strip().upper()
        if tags:
            query["tags"] = {"$all": [tag.strip().lower() for tag in tags if tag.strip()]}
        if query_text.strip():
            query["retrieval_text"] = {"$regex": query_text.strip().lower(), "$options": "i"}

        cursor = (
            self.external_knowledge_items.find(query)
            .sort("created_at", DESCENDING)
            .skip(max(0, int(offset)))
            .limit(max(1, min(int(limit), 100)))
        )
        return [item async for item in cursor]

    async def get_external_chunks(self, *, parent_item_id: str) -> list[dict]:
        cursor = self.external_knowledge_chunks.find({"parent_item_id": parent_item_id}).sort("sequence", 1)
        return [item async for item in cursor]


def _derive_external_body(item: dict) -> str:
    parts = [
        str(item.get("summary") or ""),
        str(item.get("unsafe_pattern") or ""),
        str(item.get("safe_pattern") or ""),
        str(item.get("bad_example") or ""),
        str(item.get("good_example") or ""),
        str(item.get("remediation_notes") or ""),
    ]
    return "\n\n".join(part for part in parts if part).strip()
