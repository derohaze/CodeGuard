import asyncio
import multiprocessing
from multiprocessing.process import BaseProcess

import uvicorn

from app.core.config import get_settings


def _run_embedded_worker() -> None:
    try:
        from arq import run_worker
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "QUEUE_BACKEND='arq' requires the optional queue dependencies. Install backend requirements in this Python environment."
        ) from exc

    from app.infrastructure.queue.arq_worker import WorkerSettings

    asyncio.set_event_loop(asyncio.new_event_loop())
    run_worker(WorkerSettings)


def _should_start_embedded_worker() -> bool:
    settings = get_settings()
    return settings.queue_backend == "arq" and settings.auto_start_queue_worker


def _should_enable_reload() -> bool:
    settings = get_settings()
    return settings.app_env == "development" and settings.api_workers == 1 and not _should_start_embedded_worker()


def _start_embedded_worker() -> BaseProcess | None:
    if not _should_start_embedded_worker():
        return None
    context = multiprocessing.get_context("spawn")
    worker_process = context.Process(target=_run_embedded_worker, name="codeguard-arq-worker", daemon=True)
    worker_process.start()
    return worker_process


def _stop_embedded_worker(worker_process: BaseProcess | None) -> None:
    if worker_process is None:
        return
    if worker_process.is_alive():
        worker_process.terminate()
        worker_process.join(timeout=5)
    if worker_process.is_alive():
        worker_process.kill()
        worker_process.join(timeout=5)


if __name__ == "__main__":
    settings = get_settings()
    worker_process = _start_embedded_worker()
    try:
        uvicorn.run(
            "app.main:app",
            host=settings.app_host,
            port=settings.app_port,
            workers=settings.api_workers,
            reload=_should_enable_reload(),
        )
    finally:
        _stop_embedded_worker(worker_process)
