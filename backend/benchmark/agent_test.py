"""Run a single agent test against the vuln API."""
import asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


async def main():
    from app.infrastructure.ai.agents.penetration_tester.agent import PenetrationTestAgent
    from app.infrastructure.ai.nvidia_security_client import NvidiaSecurityClient

    ai_client = NvidiaSecurityClient()
    agent = PenetrationTestAgent(ai_client=ai_client)

    history = await agent.run_interactive(
        target_info={"url": "http://127.0.0.1:9000", "type": "running_service"},
        project_name="benchmark-vuln-api",
        source_path=r"benchmark/vuln_api.py",
        scan_mode="dynamic",
        preset="full",
        enable_thinking=True,
    )

    print(f"History entries: {len(history)}")
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
                p = json.loads(content)
                if isinstance(p, dict):
                    for key in ("finding_overrides", "findings"):
                        items = p.get(key, [])
                        if isinstance(items, list):
                            findings.extend(items)
            except Exception:
                pass

    print(f"Findings: {len(findings)}")
    for f in findings:
        print(f"  - {f.get('title') or f.get('summary') or '?'} [{f.get('severity','?')}]")

    # Print assistant messages summary
    for i, msg in enumerate(history):
        if not isinstance(msg, dict):
            print(f"[{i}] {type(msg).__name__}")
            continue
        role = msg.get("role", "?")
        content = msg.get("content", "")
        tc = msg.get("tool_calls")
        print(f"[{i}] role={role}", end="")
        if content:
            c = content[:120].replace("\n", " ")
            print(f" content={c}", end="")
        if tc:
            print(f" tool_calls={len(tc)}", end="")
        print()


if __name__ == "__main__":
    asyncio.run(main())
