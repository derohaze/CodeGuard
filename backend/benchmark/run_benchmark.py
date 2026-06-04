from __future__ import annotations

"""Run the Aegix penetration testing benchmark.

This benchmark:
1. Starts the vulnerable test API on port 9000
2. Runs the agent against it (after state — current prompts)
3. Stashes current prompts, restores git HEAD prompts
4. Runs the agent again (before state — old prompts)
5. Restores current prompts
6. Prints comparison table

Usage:
    python -m benchmark.run_benchmark

Requirements:
    - NVIDIA_API_KEY set in .env
    - MongoDB running (for scan execution service)
"""

import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Ensure we can import from backend
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def run_benchmark():
    from benchmark.runner import BenchmarkRunner

    api_process = None

    try:
        # ── Step 1: Start the vulnerable test API ──────────────────────
        print("Starting vulnerable benchmark API on port 9000...")
        api_process = subprocess.Popen(
            [sys.executable, "-c", "import uvicorn; uvicorn.run('benchmark.vuln_api:app', host='127.0.0.1', port=9000, log_level='error')"],
            cwd=Path(__file__).resolve().parent.parent,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for API to be ready
        import httpx
        for attempt in range(20):
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.get("http://127.0.0.1:9000/health")
                    if r.status_code == 200:
                        print("Benchmark API is ready.")
                        break
            except Exception:
                pass
            await asyncio.sleep(1)
        else:
            print("ERROR: Benchmark API did not start within 20 seconds.")
            print("Make sure port 9000 is free and all dependencies are installed.")
            return

        runner = BenchmarkRunner()

        # ── Step 2: Run "after" benchmark (current prompts) ─────────────
        print("\n" + "=" * 60)
        print("  Running benchmark: AFTER (current prompts + reasoning)")
        print("=" * 60)
        after_result = await runner.run(
            label="after",
            target_url="http://127.0.0.1:9000",
            use_stashed_prompts=False,
            timeout_seconds=300,
        )
        print(f"  After complete: {after_result.findings_count} findings, "
              f"{after_result.total_time_seconds}s, "
              f"recall {after_result.recall}%")

        # ── Step 3: Run "before" benchmark (old prompts from git) ──────
        print("\n" + "=" * 60)
        print("  Running benchmark: BEFORE (old prompts)")
        print("=" * 60)
        before_result = await runner.run(
            label="before",
            target_url="http://127.0.0.1:9000",
            use_stashed_prompts=True,
            timeout_seconds=300,
        )
        print(f"  Before complete: {before_result.findings_count} findings, "
              f"{before_result.total_time_seconds}s, "
              f"recall {before_result.recall}%")

        # ── Step 4: Print comparison table ─────────────────────────────
        print("\n")
        runner.print_table()

    finally:
        # ── Cleanup: kill the test API ─────────────────────────────────
        if api_process:
            print("\nStopping benchmark API...")
            api_process.terminate()
            try:
                api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api_process.kill()
                api_process.wait(timeout=3)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
