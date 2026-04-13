import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.services.scan_lock_manager import ScanLockManager


class ScanLockManagerTests(unittest.TestCase):
    def test_in_memory_lock_blocks_second_submission_for_same_source(self):
        settings = type(
            "S",
            (),
            {
                "scan_lock_backend": "in_memory",
                "redis_url": None,
                "session_scan_lock_ttl_seconds": 60,
                "source_scan_lock_ttl_seconds": 60,
            },
        )()
        with patch("app.infrastructure.services.scan_lock_manager.get_settings", return_value=settings):
            manager = ScanLockManager()
            first = asyncio.run(
                manager.acquire_submission_locks(session_id="session-1", source_fingerprint="source-1")
            )
            second = asyncio.run(
                manager.acquire_submission_locks(session_id="session-2", source_fingerprint="source-1")
            )
            self.assertIsNotNone(first)
            self.assertIsNone(second)
            asyncio.run(manager.release_submission_locks(first))
            third = asyncio.run(
                manager.acquire_submission_locks(session_id="session-3", source_fingerprint="source-1")
            )
            self.assertIsNotNone(third)
            asyncio.run(manager.release_submission_locks(third))
