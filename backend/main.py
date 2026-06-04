import asyncio
import multiprocessing
import os
import shutil
import subprocess
from multiprocessing.process import BaseProcess
from pathlib import Path

import uvicorn

from app.core.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parent
NODE_GATEWAY_ROOT = BACKEND_ROOT / "node"
RESET = "\033[0m"
CYAN = "\033[36m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"

UVICORN_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": f"%(levelprefix)s {CYAN}[python-api]{RESET} %(message)s",
            "use_colors": True,
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": f'%(levelprefix)s {CYAN}[python-api]{RESET} %(client_addr)s - "%(request_line)s" %(status_code)s',
            "use_colors": True,
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
    },
}


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
    worker_process = context.Process(target=_run_embedded_worker, name="aegix-arq-worker", daemon=True)
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


def _loopback_host(host: str) -> str:
    if host in {"0.0.0.0", "::", "[::]"}:
        return "127.0.0.1"
    return host


def _find_pnpm() -> str:
    executable = shutil.which("pnpm.cmd" if os.name == "nt" else "pnpm")
    if executable is None:
        raise RuntimeError("pnpm is required to run the backend Node gateway.")
    return executable


def _ensure_node_gateway_dependencies(pnpm: str) -> None:
    if (NODE_GATEWAY_ROOT / "node_modules").exists():
        return
    subprocess.run([pnpm, "install"], cwd=NODE_GATEWAY_ROOT, check=True)


def _start_node_gateway() -> subprocess.Popen:
    settings = get_settings()
    pnpm = _find_pnpm()
    _ensure_node_gateway_dependencies(pnpm)
    env = os.environ.copy()
    env.setdefault("PYTHON_API_BASE_URL", f"http://{_loopback_host(settings.app_host)}:{settings.app_port}")
    env.setdefault("NODE_GATEWAY_HOST", "127.0.0.1")
    env.setdefault("NODE_GATEWAY_PORT", "7000")
    return subprocess.Popen(
        [pnpm, "--silent", "gateway:dev"],
        cwd=NODE_GATEWAY_ROOT,
        env=env,
    )


def _stop_node_gateway(gateway_process: subprocess.Popen | None) -> None:
    if gateway_process is None or gateway_process.poll() is not None:
        return
    gateway_process.terminate()
    try:
        gateway_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        gateway_process.kill()
        gateway_process.wait(timeout=5)


if __name__ == "__main__":
    settings = get_settings()
    worker_process = _start_embedded_worker()
    gateway_process = _start_node_gateway()
    try:
        print(
            f"{GREEN}[backend-main]{RESET} starting services | "
            f"{MAGENTA}node-gateway{RESET}=http://127.0.0.1:7000 -> "
            f"{CYAN}python-api{RESET}=http://{_loopback_host(settings.app_host)}:{settings.app_port}",
            flush=True,
        )
        uvicorn.run(
            "app.main:app",
            host=settings.app_host,
            port=settings.app_port,
            workers=settings.api_workers,
            reload=_should_enable_reload(),
            log_config=UVICORN_LOG_CONFIG,
        )
    finally:
        _stop_node_gateway(gateway_process)
        _stop_embedded_worker(worker_process)
