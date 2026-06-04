"""
Standalone benchmark script — runs the agent against the vulnerable test API.
Handles starting/stopping the test API automatically.

Usage:
    python benchmark/run_bench.py
"""
import asyncio, json, os, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def start_vuln_api():
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "benchmark.vuln_api:app",
         "--host", "127.0.0.1", "--port", "9000", "--log-level", "error"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    import httpx
    for i in range(20):
        try:
            r = httpx.get("http://127.0.0.1:9000/health", timeout=3)
            if r.status_code == 200:
                print(f"[bench] Vuln API ready (attempt {i+1})")
                return proc
        except Exception:
            pass
        await asyncio.sleep(1)
    proc.kill()
    raise RuntimeError("Vuln API failed to start")


def stop_vuln_api(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        print("[bench] Vuln API stopped")


def extract_findings(history: list) -> list[dict]:
    findings = []
    for msg in history:
        if not isinstance(msg, dict):
            continue
        for tc in msg.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function", {})
            if isinstance(fn, dict) and fn.get("name") == "confirm_finding":
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                    findings.append(args)
                except Exception:
                    pass
            if tc.get("name") == "confirm_finding":
                try:
                    args = json.loads(tc.get("arguments", "{}"))
                    findings.append(args)
                except Exception:
                    pass
        content = msg.get("content", "")
        if isinstance(content, str) and content.strip().startswith("{"):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    for key in ("finding_overrides", "findings"):
                        items = parsed.get(key, [])
                        if isinstance(items, list):
                            findings.extend(items)
            except Exception:
                pass
    return findings


async def run_agent(label: str) -> dict:
    from app.infrastructure.ai.agents.penetration_tester.agent import PenetrationTestAgent
    from app.infrastructure.ai.nvidia_security_client import NvidiaSecurityClient
    from app.core.config import get_settings

    ai_client = NvidiaSecurityClient()
    if not ai_client.is_configured(get_settings()):
        return {"error": "NVIDIA_API_KEY not configured"}

    agent = PenetrationTestAgent(ai_client=ai_client)

    start = time.monotonic()
    history = await agent.run_interactive(
        target_info={"url": "http://127.0.0.1:9000", "type": "running_service"},
        project_name="benchmark-vuln-api",
        source_path=str(ROOT / "benchmark" / "vuln_api.py"),
        scan_mode="dynamic",
        preset="full",
        enable_thinking=True,
    )
    elapsed = time.monotonic() - start

    findings = extract_findings(history)
    steps = len([m for m in history if isinstance(m, dict) and m.get("role") == "assistant"])
    tool_calls = sum(
        len(m.get("tool_calls", []) or [])
        for m in history if isinstance(m, dict) and m.get("role") == "assistant"
    )

    print(f"\n[{label}] {elapsed:.1f}s | {len(findings)} findings | {steps} steps | {tool_calls} tool calls")
    for f in findings:
        print(f"  -> {f.get('title') or f.get('summary') or '?'} [{f.get('severity','?')}]")

    return {
        "label": label,
        "elapsed": round(elapsed, 1),
        "findings": findings,
        "findings_count": len(findings),
        "steps": steps,
        "tool_calls": tool_calls,
        "history_len": len(history),
    }


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Aegix Penetration Test Benchmark")
    parser.add_argument("--both", action="store_true", help="Run before AND after comparison")
    parser.add_argument("--skip-api", action="store_true", help="Skip API startup (already running)")
    args = parser.parse_args()

    promp_dir = ROOT / "app" / "infrastructure" / "ai" / "prompts"
    stash_dir = ROOT / "app" / "infrastructure" / "ai" / ".benchmark_stash"

    api_proc = None
    if not args.skip_api:
        api_proc = await start_vuln_api()

    try:
        if not args.both:
            result = await run_agent("after")
            print(f"\nResult: {result['findings_count']} findings in {result['elapsed']}s")
            return

        # After
        print("=" * 60)
        print("  AFTER (current prompts + reasoning)")
        print("=" * 60)
        after = await run_agent("after")

        # Switch to git HEAD prompts
        print("\n" + "=" * 60)
        print("  Switching to git HEAD prompts...")
        print("=" * 60)
        import shutil, subprocess as sp
        if stash_dir.exists():
            shutil.rmtree(stash_dir)
        shutil.copytree(promp_dir, stash_dir)
        print("  [stash] saved current prompts")

        for md_file in sorted(promp_dir.glob("*.md")):
            rel = md_file.relative_to(ROOT.parent).as_posix()
            r = sp.run(["git", "show", f"HEAD:{rel}"], capture_output=True, text=True, cwd=ROOT.parent)
            if r.returncode == 0 and r.stdout.strip():
                md_file.write_text(r.stdout, encoding="utf-8")
                print(f"  [git] restored HEAD: {md_file.name}")

        # Before
        print("\n" + "=" * 60)
        print("  BEFORE (old prompts)")
        print("=" * 60)
        before = await run_agent("before")

        # Restore current
        if stash_dir.exists():
            if promp_dir.exists():
                shutil.rmtree(promp_dir)
            shutil.copytree(stash_dir, promp_dir)
            shutil.rmtree(stash_dir)
            print("\n  [stash] restored current prompts")

        # Comparison table
        print("\n\n")
        print("=" * 80)
        print("  AEGIX PENETRATION TESTING BENCHMARK RESULTS")
        print("=" * 80)
        print(f"\n  {'Metric':<35} {'Before':<12} {'After':<12} {'Change':<12}")
        print(f"  {'-'*35} {'-'*12} {'-'*12} {'-'*12}")

        def delta(b, a):
            try:
                bf, af = float(b), float(a)
                if bf == 0:
                    return "NEW" if af > 0 else "—"
                d = ((af - bf) / bf) * 100
                return f"{'↑' if d > 0 else '↓'} {abs(d):.1f}%"
            except (ValueError, TypeError):
                return "—"

        for name, bv, av in [
            ("Time (s)", before["elapsed"], after["elapsed"]),
            ("Findings", before["findings_count"], after["findings_count"]),
            ("Steps", before["steps"], after["steps"]),
            ("Tool calls", before["tool_calls"], after["tool_calls"]),
        ]:
            print(f"  {name:<35} {str(bv):<12} {str(av):<12} {delta(bv, av):<12}")

        print(f"\n  Before findings:")
        for f in before.get("findings", []):
            print(f"    - {f.get('title') or f.get('summary') or '?'} [{f.get('severity','?')}]")
        print(f"\n  After findings:")
        for f in after.get("findings", []):
            print(f"    - {f.get('title') or f.get('summary') or '?'} [{f.get('severity','?')}]")

    finally:
        if api_proc:
            stop_vuln_api(api_proc)


if __name__ == "__main__":
    asyncio.run(main())
