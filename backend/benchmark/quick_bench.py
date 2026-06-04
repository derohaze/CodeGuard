"""Quick benchmark runner — tests the current agent against the vuln API.

Usage:
    cd backend
    python benchmark/quick_bench.py [--both]
"""
import asyncio, json, os, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "app" / "infrastructure" / "ai" / "prompts"
STASH_DIR = Path(__file__).resolve().parent.parent / "app" / "infrastructure" / "ai" / ".benchmark_stash"
CWD = Path(__file__).resolve().parent.parent.parent


def extract_findings_from_history(history: list) -> list[dict]:
    """Extract confirmed findings from agent history (tool calls + final report)."""
    findings = []
    for msg in history:
        if not isinstance(msg, dict):
            continue

        # Tool calls (confirm_finding)
        tcs = msg.get("tool_calls", [])
        if isinstance(tcs, list):
            for tc in tcs:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function", {})
                if isinstance(fn, dict) and fn.get("name") == "confirm_finding":
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                        findings.append(args)
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Also handle normalized flat format
                if tc.get("name") == "confirm_finding":
                    try:
                        args = json.loads(tc.get("arguments", "{}"))
                        findings.append(args)
                    except (json.JSONDecodeError, TypeError):
                        pass

        # Assistant message content (final JSON report)
        content = msg.get("content", "")
        if isinstance(content, str) and len(content) > 50:
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    fo = parsed.get("finding_overrides", [])
                    if isinstance(fo, list):
                        findings.extend(fo)
                    fs = parsed.get("findings", [])
                    if isinstance(fs, list):
                        findings.extend(fs)
            except (json.JSONDecodeError, TypeError):
                pass

        # Tool results (findings tool output)
        if msg.get("role") == "tool" and isinstance(msg.get("content"), str):
            try:
                tc_result = json.loads(msg["content"])
                if isinstance(tc_result, dict) and "finding" in tc_result:
                    findings.append(tc_result["finding"])
            except (json.JSONDecodeError, TypeError):
                pass

    return findings


async def run_single(label: str) -> dict:
    from app.infrastructure.ai.agents.penetration_tester.agent import PenetrationTestAgent
    from app.infrastructure.ai.nvidia_security_client import NvidiaSecurityClient

    ai_client = NvidiaSecurityClient()
    agent = PenetrationTestAgent(ai_client=ai_client)

    penetration_context = {
        "project_name": "benchmark-vuln-api",
        "source_path": str(Path(__file__).resolve().parent / "vuln_api.py"),
        "target": {"url": "http://127.0.0.1:9000", "type": "running_service"},
        "interactive": True,
        "preset": "full",
        "scan_mode": "dynamic",
        "session_id": f"benchmark-{label}-{int(time.time())}",
    }

    start = time.monotonic()

    # Call run_interactive directly to get raw history
    history = await agent.run_interactive(
        target_info=penetration_context.get("target", {}),
        project_name=penetration_context.get("project_name", ""),
        source_path=penetration_context.get("source_path", ""),
        scan_mode=penetration_context.get("scan_mode", ""),
        preset=penetration_context.get("preset", ""),
        enable_thinking=True,
    )

    elapsed = time.monotonic() - start
    findings = extract_findings_from_history(history)

    steps = len([m for m in history if isinstance(m, dict) and m.get("role") == "assistant"])
    tool_calls = sum(
        len(m.get("tool_calls", []) or [])
        for m in history if isinstance(m, dict) and m.get("role") == "assistant"
    )

    print(f"\n  [{label}] completed in {elapsed:.1f}s | "
          f"{len(findings)} findings | {steps} steps | {tool_calls} tool calls | "
          f"{len(history)} history entries")

    # Print findings details
    for f in findings:
        print(f"    -> {f.get('title', f.get('summary', '?')[:60])} [{f.get('severity','?')}]")

    return {
        "label": label,
        "elapsed": round(elapsed, 1),
        "findings_count": len(findings),
        "findings": findings,
        "steps": steps,
        "tool_calls": tool_calls,
        "history_len": len(history),
    }


def stash_prompts():
    import shutil
    if STASH_DIR.exists():
        shutil.rmtree(STASH_DIR)
    shutil.copytree(PROMPTS_DIR, STASH_DIR)
    print("  [stash] current prompts saved")


def restore_git_prompts():
    for md_file in sorted(PROMPTS_DIR.glob("*.md")):
        rel = md_file.relative_to(CWD).as_posix()
        result = subprocess.run(
            ["git", "show", f"HEAD:{rel}"],
            capture_output=True, text=True, cwd=CWD,
        )
        if result.returncode == 0 and result.stdout.strip():
            md_file.write_text(result.stdout, encoding="utf-8")
            print(f"  [git] restored HEAD: {md_file.name}")
        else:
            print(f"  [git] WARNING: could not restore {md_file.name}: {result.stderr.strip()}")


def restore_stashed_prompts():
    import shutil
    if STASH_DIR.exists():
        if PROMPTS_DIR.exists():
            shutil.rmtree(PROMPTS_DIR)
        shutil.copytree(STASH_DIR, PROMPTS_DIR)
        shutil.rmtree(STASH_DIR)
        print("  [stash] restored current prompts")


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--both", action="store_true", help="Run before AND after")
    parser.add_argument("--timeout", type=int, default=300, help="Per-run timeout (seconds)")
    args = parser.parse_args()

    # Verify NVIDIA API key is configured
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.nvidia_api_key and not settings.nvidia_api_keys:
        print("ERROR: NVIDIA_API_KEY not configured in .env")
        return

    if not args.both:
        print("BENCHMARK: AFTER (current prompts + reasoning)")
        print("=" * 60)
        result = await run_single("after")
        print(f"\nResult summary: {result['findings_count']} findings in {result['elapsed']}s")
        return

    # ── Run "after" first ──
    print("=" * 60)
    print("  BENCHMARK: AFTER (current prompts + reasoning)")
    print("=" * 60)
    after = await run_single("after")

    # ── Stash current, restore git HEAD ──
    print("\n" + "=" * 60)
    print("  Switching to git HEAD prompts (BEFORE state)")
    print("=" * 60)
    stash_prompts()
    restore_git_prompts()

    # ── Run "before" ──
    print("\n" + "=" * 60)
    print("  BENCHMARK: BEFORE (old prompts)")
    print("=" * 60)
    before = await run_single("before")

    # ── Restore current prompts ──
    restore_stashed_prompts()

    # ── Print comparison ──
    print("\n\n")
    print("=" * 80)
    print("  AEGIX PENETRATION TESTING BENCHMARK RESULTS")
    print("=" * 80)
    print(f"\n  {'Metric':<35} {'Before':<12} {'After':<12} {'Change':<12}")
    print(f"  {'-'*35} {'-'*12} {'-'*12} {'-'*12}")

    def pct(b, a):
        try:
            bf, af = float(b), float(a)
            if bf == 0:
                return "NEW" if af > 0 else "—"
            diff = ((af - bf) / bf) * 100
            arrow = "↑" if diff > 0 else "↓"
            return f"{arrow} {abs(diff):.1f}%"
        except (ValueError, TypeError):
            return "—"

    metrics = [
        ("Time (s)", before.get("elapsed", "?"), after.get("elapsed", "?")),
        ("Findings", before.get("findings_count", "?"), after.get("findings_count", "?")),
        ("Steps", before.get("steps", "?"), after.get("steps", "?")),
        ("Tool calls", before.get("tool_calls", "?"), after.get("tool_calls", "?")),
        ("History messages", before.get("history_len", "?"), after.get("history_len", "?")),
    ]
    for name, b, a in metrics:
        print(f"  {name:<35} {str(b):<12} {str(a):<12} {pct(b, a):<12}")

    print(f"\n  Before findings:")
    for f in before.get("findings", []):
        print(f"    - {f.get('title', f.get('summary', '?'))[:80]} [{f.get('severity','?')}]")
    print(f"\n  After findings:")
    for f in after.get("findings", []):
        print(f"    - {f.get('title', f.get('summary', '?'))[:80]} [{f.get('severity','?')}]")


if __name__ == "__main__":
    asyncio.run(main())
