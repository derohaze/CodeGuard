import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.queue.scan_job_dispatcher import ArqScanJobDispatcher, InProcessScanJobDispatcher


class FakeScanExecutionService:
    def __init__(self) -> None:
        self.submit = AsyncMock()


class FakeArqPool:
    def __init__(self) -> None:
        self.enqueue_job = AsyncMock()


class ScanJobDispatcherTests(unittest.TestCase):
    def test_in_process_dispatcher_submits_job_locally(self):
        service = FakeScanExecutionService()
        dispatcher = InProcessScanJobDispatcher(service)

        asyncio.run(dispatcher.enqueue_scan("session-1", "job-1"))

        service.submit.assert_awaited_once_with("session-1", job_id="job-1")

    def test_arq_dispatcher_enqueues_job_on_named_queue(self):
        pool = FakeArqPool()
        dispatcher = ArqScanJobDispatcher("khwarizm:queue:scan")

        with patch("app.infrastructure.queue.scan_job_dispatcher.get_arq_pool", AsyncMock(return_value=pool)):
            asyncio.run(dispatcher.enqueue_scan("session-1", "job-1"))

        pool.enqueue_job.assert_awaited_once_with(
            "run_scan_job",
            "session-1",
            "job-1",
            _queue_name="khwarizm:queue:scan",
            _job_id="scan:job-1",
        )


if __name__ == "__main__":
    unittest.main()
