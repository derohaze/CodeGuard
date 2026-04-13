import asyncio
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.settings.runtime_settings_service import RuntimeSettingsService


class InMemoryRuntimeSettingsRepository:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.document = {
            "_id": "global",
            "default_preset": "balanced",
            "default_scan_mode": "deep",
            "auto_open_results": True,
            "remember_sidebar_state": True,
            "motion_profile": "fluid",
            "theme": "light",
            "surface_contrast": "soft",
            "remediation_max_attempts": 3,
            "remediation_reuse_explanation": True,
            "external_ingestion_max_rps": 10,
            "external_ingestion_retry_attempts": 3,
            "external_ingestion_backoff_seconds": 0.5,
            "created_at": now,
            "updated_at": now,
        }
        self.get_calls = 0

    async def get(self):
        self.get_calls += 1
        return dict(self.document)

    async def update(self, updates):
        self.document.update(updates)
        self.document["updated_at"] = datetime.now(UTC)
        return dict(self.document)


class RuntimeSettingsServiceTests(unittest.TestCase):
    def test_get_uses_cache_between_calls(self):
        repository = InMemoryRuntimeSettingsRepository()
        service = RuntimeSettingsService(repository, cache_ttl_seconds=10.0)

        first = asyncio.run(service.get())
        second = asyncio.run(service.get())

        self.assertEqual(first.default_scan_mode, "deep")
        self.assertEqual(second.default_scan_mode, "deep")
        self.assertEqual(repository.get_calls, 1)

    def test_update_overrides_values(self):
        repository = InMemoryRuntimeSettingsRepository()
        service = RuntimeSettingsService(repository, cache_ttl_seconds=10.0)

        updated = asyncio.run(service.update({"remediation_max_attempts": 2, "default_scan_mode": "fast"}))
        fetched = asyncio.run(service.get())

        self.assertEqual(updated.remediation_max_attempts, 2)
        self.assertEqual(updated.default_scan_mode, "fast")
        self.assertEqual(fetched.remediation_max_attempts, 2)
        self.assertEqual(fetched.default_scan_mode, "fast")


if __name__ == "__main__":
    unittest.main()
