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
from app.infrastructure.learning.fingerprints import text_checksum
from app.infrastructure.learning.ingestion_validation import (
    sanitize_external_item,
    validate_external_source_spec,
)
from app.infrastructure.learning.normalization import normalize_external_item
from app.infrastructure.learning.repository import LearningArchiveMongoRepository
from app.infrastructure.learning.schemas import ExternalKnowledgeSourceSpec
from app.infrastructure.settings.runtime_settings_service import RuntimeSettingsService


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

    async def fetch(
        self,
        endpoint: str,
        *,
        requests_per_second: int | None = None,
        retry_attempts: int | None = None,
        backoff_seconds: float | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        active_timeout = float(timeout_seconds or self.timeout_seconds)
        active_retry_attempts = max(1, int(retry_attempts or self.retry_attempts))
        active_backoff = float(backoff_seconds or self.backoff_seconds)
        async with httpx.AsyncClient(timeout=active_timeout) as client:
            for attempt in range(1, active_retry_attempts + 1):
                try:
                    await self._respect_rate_limit(requests_per_second=requests_per_second)
                    response = await client.get(endpoint)
                    response.raise_for_status()
                    return response.text
                except httpx.HTTPStatusError as exc:
                    if attempt >= active_retry_attempts or exc.response.status_code < 500:
                        raise
                    await asyncio.sleep(self._backoff_delay(attempt, active_backoff))
                except httpx.HTTPError:
                    if attempt >= active_retry_attempts:
                        raise
                    await asyncio.sleep(self._backoff_delay(attempt, active_backoff))
        raise RuntimeError("External ingestion failed after retries.")

    async def _respect_rate_limit(self, *, requests_per_second: int | None = None) -> None:
        active_rps = max(1, int(requests_per_second or self.max_requests_per_second))
        async with self._guard:
            minimum_interval = 1.0 / active_rps
            now = time.monotonic()
            elapsed = now - self._last_request_at
            if elapsed < minimum_interval:
                await asyncio.sleep(minimum_interval - elapsed)
            self._last_request_at = time.monotonic()

    def _backoff_delay(self, attempt: int, base_backoff_seconds: float) -> float:
        # Exponential backoff with lightweight jitter.
        return float(base_backoff_seconds) * (2 ** (attempt - 1)) + (0.1 * attempt)


class ExternalKnowledgeIngestionService:
    def __init__(
        self,
        repository: LearningArchiveMongoRepository,
        fetcher: HttpExternalSourceFetcher | None = None,
        runtime_settings_service: RuntimeSettingsService | None = None,
    ) -> None:
        self.repository = repository
        self.fetcher = fetcher or HttpExternalSourceFetcher()
        self.runtime_settings_service = runtime_settings_service

    async def ingest(self, sources: list[ExternalKnowledgeSourceSpec]) -> IngestionSummary:
        run_id = f"ingest_{uuid4().hex}"
        written = 0
        skipped = 0
        failed = 0
        logger.info("learning_ingestion_started", extra={"run_id": run_id, "source_count": len(sources)})
        runtime_settings = await self.runtime_settings_service.get() if self.runtime_settings_service is not None else None
        runtime_max_rps = int(runtime_settings.external_ingestion_max_rps) if runtime_settings is not None else None
        runtime_retry_attempts = int(runtime_settings.external_ingestion_retry_attempts) if runtime_settings is not None else None
        runtime_backoff_seconds = float(runtime_settings.external_ingestion_backoff_seconds) if runtime_settings is not None else None

        for source in sources:
            source_name = source.source_name.strip().lower()
            try:
                validate_external_source_spec(source)
                await self.repository.upsert_external_source(source.model_dump())
                effective_requests_per_second = source.requests_per_second or runtime_max_rps
                raw_text = await self.fetcher.fetch(
                    source.endpoint,
                    requests_per_second=effective_requests_per_second,
                    retry_attempts=runtime_retry_attempts,
                    backoff_seconds=runtime_backoff_seconds,
                )
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
                        sanitized = sanitize_external_item(raw_item)
                        normalized = normalize_external_item(
                            source=source,
                            raw_item=sanitized.item,
                            ingestion_run_id=run_id,
                        )
                        item_id, inserted = await self.repository.upsert_external_item(
                            ingestion_run_id=run_id,
                            item=normalized.model_dump(),
                            large_body=_build_external_large_body(sanitized.item),
                            body_type=_detect_body_type(sanitized.item),
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
                        "raw_payload_checksum": text_checksum(raw_text),
                        "parser_name": parsed_payload.parser_name,
                        "parser_warnings": parsed_payload.warnings,
                        "rate_limit_rps": effective_requests_per_second or getattr(self.fetcher, "max_requests_per_second", None),
                        "retry_attempts": runtime_retry_attempts or getattr(self.fetcher, "retry_attempts", None),
                        "backoff_seconds": runtime_backoff_seconds or getattr(self.fetcher, "backoff_seconds", None),
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
