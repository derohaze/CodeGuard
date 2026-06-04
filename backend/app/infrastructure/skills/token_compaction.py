from __future__ import annotations

"""
Token-aware auto-compaction with circuit breaker pattern.
Ported from PentesterFlow's agent.ts auto-compaction logic.
"""

import logging

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_FAILURES = 3
COMPACTION_INPUT_CHAR_LIMIT = 22000

COMPACTION_SYSTEM_PROMPT = (
    "Create a compact continuation memory for the same security analysis session. "
    "Use concise Markdown with exactly these headings: "
    "Current objective, Target and scope, Decisions and assumptions, "
    "Tested surface, Findings and evidence, Files and commands, "
    "Credentials and placeholders, Open TODOs, Next best actions. "
    "Preserve exact IDs, files, commands, tool results that matter, "
    "confirmed negatives, and reproduction evidence. "
    "Redact secrets but keep stable placeholders. "
    "Omit chatter and failed dead ends unless they prevent repeat work."
)


class TokenCompactor:
    def __init__(self, threshold: int = 16000):
        self.threshold = threshold
        self.consecutive_failures = 0

    def approx_tokens(self, messages: list[dict]) -> int:
        total = 0
        for m in messages:
            content = m.get("content", "") or ""
            total += len(content) // 4
            for tc in m.get("tool_calls", []):
                fn = tc.get("function", {})
                total += (len(fn.get("name", "")) + len(fn.get("arguments", ""))) // 4
        return total

    def should_compact(self, approx_tokens: int) -> bool:
        return (
            self.threshold > 0
            and self.consecutive_failures < MAX_CONSECUTIVE_FAILURES
            and approx_tokens >= self.threshold
        )

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        logger.warning("compaction failure %d/%d", self.consecutive_failures, MAX_CONSECUTIVE_FAILURES)

    def record_success(self) -> None:
        self.consecutive_failures = 0

    @staticmethod
    def build_compaction_request(history: list[dict]) -> dict:
        history_snap = history[:]
        compacted = _bounded_history(history_snap)
        return {
            "model": "",  # filled by caller
            "messages": [
                {"role": "system", "content": COMPACTION_SYSTEM_PROMPT},
                {"role": "user", "content": compacted},
            ],
        }

    @staticmethod
    def format_history(history: list[dict]) -> str:
        lines: list[str] = []
        for m in history:
            if not m.get("content") and not m.get("tool_calls"):
                continue
            role = m.get("role", "")
            name = m.get("name", "")
            label = f"\n[{role}:{name}]" if name else f"\n[{role}]"
            lines.append(label)
            if m.get("content"):
                lines.append(m["content"])
            for tc in m.get("tool_calls", []):
                lines.append(f"tool_call {tc.get('id', '')} {tc.get('function', {}).get('name', '')} {tc.get('function', {}).get('arguments', '')}")
        return "\n".join(lines)


def _bounded_history(history: list[dict]) -> str:
    full = TokenCompactor.format_history(history)
    if len(full) <= COMPACTION_INPUT_CHAR_LIMIT:
        return full
    tail = full[-COMPACTION_INPUT_CHAR_LIMIT:]
    boundary = tail.find("\n[")
    trimmed = tail[boundary:] if boundary > 0 else tail
    return (
        f"[system]\nOlder conversation text was omitted because the compaction input "
        f"exceeded {COMPACTION_INPUT_CHAR_LIMIT} characters.\n"
        f"{trimmed}"
    )
