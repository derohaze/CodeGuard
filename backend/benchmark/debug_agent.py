"""Debug the agent history to understand what's happening."""
import asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def debug_agent():
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
        "session_id": f"benchmark-debug-{int(asyncio.get_event_loop().time())}",
    }

    history = await agent.run(penetration_context)

    print(f"\nHistory length: {len(history)}\n")
    for i, msg in enumerate(history):
        if not isinstance(msg, dict):
            print(f"[{i}] TYPE: {type(msg).__name__}, VALUE: {str(msg)[:200]}")
            continue
        role = msg.get("role", "?")
        content = msg.get("content", "")
        tc = msg.get("tool_calls")
        finish = msg.get("finish_reason", "")

        print(f"[{i}] role={role}", end="")
        if content:
            print(f" content={str(content)[:300]}", end="")
        if tc:
            print(f" tool_calls={len(tc)}", end="")
        if finish:
            print(f" finish={finish}", end="")
        print()

    # Check if there's a report embedded
    for msg in reversed(history):
        if isinstance(msg, dict):
            c = msg.get("content", "")
            if isinstance(c, str) and ("executive_summary" in c or "finding" in c.lower()):
                print("\n\n=== Possible report found ===")
                print(c[:2000])
                break


if __name__ == "__main__":
    asyncio.run(debug_agent())
