from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import get_settings
from app.infrastructure.learning.external_parsers import (
    ParsedExternalPayload,
    parse_external_payload_with_parser,
)
from app.infrastructure.learning.normalization import normalize_external_item
from app.infrastructure.learning.repository import LearningArchiveMongoRepository
from app.infrastructure.learning.schemas import ExternalKnowledgeSourceSpec


logger = logging.getLogger("codeguard.learning.ingestion")


@dataclass(slots=True)
class IngestionSummary:
    run_id: str
    source_count: int
    item_written: int
    item_skipped: int
    item_failed: int
    status: str


class HttpExternalSourceFetcher:
    def __init__(self) -> None:
        settings = get_settings()
        self.max_requests_per_second = max(1, int(settings.external_ingestion_max_rps))
        self.retry_attempts = max(1, int(settings.external_ingestion_retry_attempts))
        self.backoff_seconds = float(settings.external_ingestion_backoff_seconds)
        self.timeout_seconds = float(settings.external_ingestion_timeout_seconds)
        self._guard = asyncio.Lock()
        self._last_request_at = 0.0

    async def fetch(self, endpoint: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(1, self.retry_attempts + 1):
                try:
                    await self._respect_rate_limit()
                    response = await client.get(endpoint)
                    response.raise_for_status()
                    return response.text
                except httpx.HTTPStatusError as exc:
                    if attempt >= self.retry_attempts or exc.response.status_code < 500:
                        raise
                    await asyncio.sleep(self._backoff_delay(attempt))
                except httpx.HTTPError:
                    if attempt >= self.retry_attempts:
                        raise
                    await asyncio.sleep(self._backoff_delay(attempt))
        raise RuntimeError("External ingestion failed after retries.")

    async def _respect_rate_limit(self) -> None:
        async with self._guard:
            minimum_interval = 1.0 / self.max_requests_per_second
            now = time.monotonic()
            elapsed = now - self._last_request_at
            if elapsed < minimum_interval:
                await asyncio.sleep(minimum_interval - elapsed)
            self._last_request_at = time.monotonic()

    def _backoff_delay(self, attempt: int) -> float:
        # Exponential backoff with lightweight jitter.
        return self.backoff_seconds * (2 ** (attempt - 1)) + (0.1 * attempt)


class ExternalKnowledgeIngestionService:
    def __init__(
        self,
        repository: LearningArchiveMongoRepository,
        fetcher: HttpExternalSourceFetcher | None = None,
    ) -> None:
        self.repository = repository
        self.fetcher = fetcher or HttpExternalSourceFetcher()

    async def ingest(self, sources: list[ExternalKnowledgeSourceSpec]) -> IngestionSummary:
        run_id = f"ingest_{uuid4().hex}"
        written = 0
        skipped = 0
        failed = 0
        logger.info("learning_ingestion_started", extra={"run_id": run_id, "source_count": len(sources)})

        for source in sources:
            source_name = source.source_name.strip().lower()
            try:
                await self.repository.upsert_external_source(source.model_dump())
                raw_text = await self.fetcher.fetch(source.endpoint)
                raw_cache_ref = await self.repository.cache_external_raw_payload(
                    ingestion_run_id=run_id,
                    source_name=source.source_name,
                    source_version=source.source_version,
                    payload_text=raw_text,
                )
                parsed_payload: ParsedExternalPayload = parse_external_payload_with_parser(
                    raw_text,
                    source_name=source_name,
                )
                raw_items = parsed_payload.items
                item_written = 0
                item_skipped = 0
                item_failed = 0
                for index, raw_item in enumerate(raw_items):
                    try:
                        normalized = normalize_external_item(
                            source=source,
                            raw_item=raw_item,
                            ingestion_run_id=run_id,
                        )
                        item_id, inserted = await self.repository.upsert_external_item(
                            ingestion_run_id=run_id,
                            item=normalized.model_dump(),
                            large_body=_build_external_large_body(raw_item),
                            body_type=_detect_body_type(raw_item),
                        )
                        logger.info(
                            "learning_ingestion_item_processed",
                            extra={
                                "run_id": run_id,
                                "source_name": source_name,
                                "item_index": index,
                                "item_id": item_id,
                                "inserted": inserted,
                            },
                        )
                        if inserted:
                            written += 1
                            item_written += 1
                        else:
                            skipped += 1
                            item_skipped += 1
                    except Exception as item_exc:
                        failed += 1
                        item_failed += 1
                        await self.repository.record_normalization_failure(
                            run_id=run_id,
                            source_name=source_name,
                            item_ref=str(raw_item.get("id") or raw_item.get("title") or index),
                            error_message=str(item_exc),
                            payload_excerpt=str(raw_item)[:1024],
                        )

                await self.repository.create_ingestion_audit(
                    run_id=run_id,
                    source_name=source_name,
                    status="completed",
                    details={
                        "source_version": source.source_version,
                        "fetched_items": len(raw_items),
                        "payload_bytes": len(raw_text.encode("utf-8")),
                        "parser_name": parsed_payload.parser_name,
                        "parser_warnings": parsed_payload.warnings,
                        "written_items": item_written,
                        "skipped_items": item_skipped,
                        "failed_items": item_failed,
                        "raw_cache_ref": raw_cache_ref,
                    },
                )
            except Exception as exc:
                failed += 1
                logger.exception("learning_ingestion_source_failed", extra={"run_id": run_id, "source_name": source_name})
                await self.repository.create_ingestion_audit(
                    run_id=run_id,
                    source_name=source_name,
                    status="failed",
                    details={"error": str(exc)},
                )

        status = "completed" if failed == 0 else "completed_with_failures"
        logger.info(
            "learning_ingestion_finished",
            extra={
                "run_id": run_id,
                "source_count": len(sources),
                "item_written": written,
                "item_skipped": skipped,
                "item_failed": failed,
                "status": status,
            },
        )
        return IngestionSummary(
            run_id=run_id,
            source_count=len(sources),
            item_written=written,
            item_skipped=skipped,
            item_failed=failed,
            status=status,
        )


def _detect_body_type(raw_item: dict[str, Any]) -> str:
    examples = " ".join(
        str(raw_item.get(key) or "")
        for key in ("bad_example", "good_example", "unsafe_pattern", "safe_pattern")
    ).lower()
    if "def " in examples or "class " in examples or "function " in examples or "select " in examples:
        return "code"
    return "prose"


def _build_external_large_body(raw_item: dict[str, Any]) -> str:
    fields = [
        raw_item.get("summary"),
        raw_item.get("description"),
        raw_item.get("unsafe_pattern"),
        raw_item.get("safe_pattern"),
        raw_item.get("bad_example"),
        raw_item.get("good_example"),
        raw_item.get("remediation_notes"),
    ]
    return "\n\n".join(str(item) for item in fields if item).strip()


def parse_external_payload(payload_text: str, *, source_name: str | None = None) -> list[dict[str, Any]]:
    # Compatibility wrapper used by existing tests and callers.
    return parse_external_payload_with_parser(payload_text, source_name=source_name).items
