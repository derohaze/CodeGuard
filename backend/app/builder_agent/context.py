from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import re

from app.core.config import get_settings


BASE_CONTEXT_TOKENS = 120
MESSAGE_ROLE_OVERHEAD_TOKENS = 10
ROLLING_SUMMARY_BASE_TOKENS = 120
MEMORY_RETRIEVAL_BASE_TOKENS = 110
PLAN_MODE_TOKENS = 90
ATTACHMENT_CONTEXT_TOKENS = 180

PREFERENCE_HINTS = (
    "prefer",
    "i want",
    "please keep",
    "\u064a\u0627\u0631\u064a\u062a",
    "\u0623\u0641\u0636\u0644",
    "\u0627\u0641\u0636\u0644",
    "\u0639\u0627\u064a\u0632",
    "\u0623\u0631\u064a\u062f",
)
CONSTRAINT_HINTS = (
    "must",
    "must not",
    "do not",
    "don't",
    "never",
    "without",
    "\u0644\u0627\u0632\u0645",
    "\u0645\u0645\u0646\u0648\u0639",
    "\u0627\u0648\u0639\u0649",
    "\u0628\u062f\u0648\u0646",
)
DECISION_HINTS = (
    "use ",
    "keep ",
    "remove ",
    "rename ",
    "we will",
    "ship ",
    "\u0627\u0639\u0645\u0644",
    "\u062e\u0644\u064a",
    "\u0634\u064a\u0644",
    "\u0647\u0646\u0639\u0645\u0644",
    "\u0627\u0633\u062a\u062e\u062f\u0645",
)

BASE_SYSTEM_PROMPT = """You are Khwarizm Builder, a production-grade AI agent operating in a structured context pipeline.

Source priority:
1. latest user message
2. recent conversation turns
3. rolling summary
4. retrieved memory
5. general reasoning only when needed

Rules:
- use memory only when it is relevant
- if sources conflict, trust the higher-priority source
- do not invent hidden memory, prior decisions, or missing context
- preserve relevant goals, preferences, constraints, and decisions when useful
- be direct, practical, and reliable
"""


@dataclass(slots=True)
class PreparedBuilderContext:
    provider_messages: list[dict[str, str]]
    context_state: dict


@dataclass(slots=True)
class BuilderTokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class BuilderContextManager:
    def __init__(self, repository) -> None:
        self.repository = repository

    async def prepare_context(
        self,
        *,
        workspace_id: str,
        thread_id: str,
        permission_mode: str,
        plan_mode: bool,
        response_speed: str,
        attachment_count: int = 0,
    ) -> PreparedBuilderContext:
        settings = get_settings()
        all_messages = await self.repository.list_messages(thread_id)
        recent_messages = all_messages[-settings.builder_chat_max_history_messages :]
        older_messages = all_messages[:-settings.builder_chat_summary_window_messages]
        stored_context = await self.repository.get_thread_context(thread_id)
        rolling_summary = _build_rolling_summary(
            older_messages[-settings.builder_chat_summary_window_messages :],
            stored_summary=str(stored_context.get("rolling_summary", "")) if stored_context else "",
        )
        memory_items = await self.repository.list_memory_items(workspace_id, limit=64)
        latest_user_text = _latest_user_message_text(all_messages)
        relevant_memory = _select_relevant_memory(
            memory_items,
            current_message=latest_user_text,
            thread_id=thread_id,
            limit=settings.builder_chat_max_memory_items,
        )
        provider_messages = [
            {
                "role": "system",
                "content": _build_system_prompt(
                    rolling_summary=rolling_summary,
                    memory_items=relevant_memory,
                    permission_mode=permission_mode,
                    plan_mode=plan_mode,
                    response_speed=response_speed,
                ),
            }
        ]
        provider_messages.extend(
            {
                "role": str(message["role"]),
                "content": str(message["text"]),
            }
            for message in recent_messages
            if str(message.get("role")) in {"user", "assistant"}
        )
        context_state = _build_context_state(
            rolling_summary=rolling_summary,
            recent_messages=recent_messages,
            relevant_memory=relevant_memory,
            permission_mode=permission_mode,
            plan_mode=plan_mode,
            attachment_count=attachment_count,
            max_tokens=settings.builder_chat_context_token_budget,
        )
        return PreparedBuilderContext(provider_messages=provider_messages, context_state=context_state)

    async def record_completion(
        self,
        *,
        workspace_id: str,
        thread_id: str,
        permission_mode: str,
        plan_mode: bool,
        attachment_count: int = 0,
        provider_usage: BuilderTokenUsage | None = None,
    ) -> dict:
        settings = get_settings()
        all_messages = await self.repository.list_messages(thread_id)
        recent_messages = all_messages[-settings.builder_chat_max_history_messages :]
        older_messages = all_messages[:-settings.builder_chat_summary_window_messages]
        rolling_summary = _build_rolling_summary(older_messages[-settings.builder_chat_summary_window_messages :])

        latest_user_message = _latest_user_message(all_messages)
        if latest_user_message is not None:
            for item in _extract_memory_items(
                workspace_id=workspace_id,
                thread_id=thread_id,
                source_message=latest_user_message,
            ):
                await self.repository.upsert_memory_item(**item)

        memory_items = await self.repository.list_memory_items(workspace_id, limit=64)
        relevant_memory = _select_relevant_memory(
            memory_items,
            current_message=_latest_user_message_text(all_messages),
            thread_id=thread_id,
            limit=settings.builder_chat_max_memory_items,
        )
        context_state = _build_context_state(
            rolling_summary=rolling_summary,
            recent_messages=recent_messages,
            relevant_memory=relevant_memory,
            permission_mode=permission_mode,
            plan_mode=plan_mode,
            attachment_count=attachment_count,
            max_tokens=settings.builder_chat_context_token_budget,
            provider_usage=provider_usage,
        )
        await self.repository.upsert_thread_context(
            thread_id=thread_id,
            workspace_id=workspace_id,
            rolling_summary=rolling_summary,
            used_tokens=context_state["used_tokens"],
            max_tokens=context_state["max_tokens"],
            percentage=context_state["percentage"],
            recent_message_count=context_state["recent_message_count"],
            memory_count=context_state["memory_count"],
            last_message_at=all_messages[-1]["created_at"] if all_messages else None,
            usage_source=context_state["usage_source"],
            provider_input_tokens=context_state["provider_input_tokens"],
            provider_output_tokens=context_state["provider_output_tokens"],
            provider_total_tokens=context_state["provider_total_tokens"],
        )
        return context_state

    async def get_thread_context_state(self, *, workspace_id: str, thread_id: str) -> dict | None:
        settings = get_settings()
        stored = await self.repository.get_thread_context(thread_id)
        memory_items = await self.repository.list_memory_items(workspace_id, limit=32)
        relevant_memory = _select_relevant_memory(
            memory_items,
            current_message="",
            thread_id=thread_id,
            limit=settings.builder_chat_max_memory_items,
        )
        if stored is None:
            messages = await self.repository.list_messages(thread_id)
            if not messages and not relevant_memory:
                return None
            return _build_context_state(
                rolling_summary="",
                recent_messages=messages[-settings.builder_chat_max_history_messages :],
                relevant_memory=relevant_memory,
                permission_mode="full-access",
                plan_mode=False,
                attachment_count=0,
                max_tokens=settings.builder_chat_context_token_budget,
            )
        return {
            "percentage": int(stored.get("percentage", 0)),
            "used_tokens": int(stored.get("used_tokens", 0)),
            "max_tokens": int(stored.get("max_tokens", settings.builder_chat_context_token_budget)),
            "rolling_summary": str(stored.get("rolling_summary", "")),
            "recent_message_count": int(stored.get("recent_message_count", 0)),
            "memory_count": len(relevant_memory),
            "memory_items": [_serialize_memory_item(item) for item in relevant_memory],
            "usage_source": str(stored.get("usage_source", "estimated")),
            "provider_input_tokens": _coerce_optional_int(stored.get("provider_input_tokens")),
            "provider_output_tokens": _coerce_optional_int(stored.get("provider_output_tokens")),
            "provider_total_tokens": _coerce_optional_int(stored.get("provider_total_tokens")),
            "updated_at": stored.get("updated_at"),
        }


def _build_system_prompt(
    *,
    rolling_summary: str,
    memory_items: list[dict],
    permission_mode: str,
    plan_mode: bool,
    response_speed: str,
) -> str:
    sections = [BASE_SYSTEM_PROMPT.strip()]
    sections.append(
        "\nExecution state:\n"
        f"- permission_mode: {permission_mode}\n"
        f"- plan_mode: {'enabled' if plan_mode else 'disabled'}\n"
        f"- response_speed: {response_speed}"
    )
    if rolling_summary:
        sections.append(f"\nRolling summary:\n{rolling_summary}")
    if memory_items:
        rendered = "\n".join(
            f"- [{item['memory_class']}] {item['title']}: {item['content']}"
            for item in memory_items
        )
        sections.append(f"\nRetrieved memory:\n{rendered}")
    return "\n".join(sections).strip()


def _build_context_state(
    *,
    rolling_summary: str,
    recent_messages: list[dict],
    relevant_memory: list[dict],
    permission_mode: str,
    plan_mode: bool,
    attachment_count: int,
    max_tokens: int,
    provider_usage: BuilderTokenUsage | None = None,
) -> dict:
    recent_message_tokens = sum(
        _estimate_text_tokens(str(message.get("text", ""))) + MESSAGE_ROLE_OVERHEAD_TOKENS
        for message in recent_messages
    )
    summary_tokens = 0
    if rolling_summary:
        summary_tokens = min(
            880,
            ROLLING_SUMMARY_BASE_TOKENS + round(_estimate_text_tokens(rolling_summary) * 0.8),
        )
    memory_tokens = 0
    if relevant_memory:
        memory_tokens = MEMORY_RETRIEVAL_BASE_TOKENS + sum(
            _estimate_text_tokens(f"{item.get('title', '')} {item.get('content', '')}")
            for item in relevant_memory
        )
    estimated_used_tokens = (
        BASE_CONTEXT_TOKENS
        + recent_message_tokens
        + summary_tokens
        + memory_tokens
        + (attachment_count * ATTACHMENT_CONTEXT_TOKENS)
        + (PLAN_MODE_TOKENS if plan_mode else 0)
    )
    provider_input_tokens = provider_usage.input_tokens if provider_usage else None
    provider_output_tokens = provider_usage.output_tokens if provider_usage else None
    provider_total_tokens = provider_usage.total_tokens if provider_usage else None
    used_tokens = estimated_used_tokens
    usage_source = "estimated"
    if provider_input_tokens is not None:
        used_tokens = provider_input_tokens
        usage_source = "provider_reported"
    elif provider_total_tokens is not None:
        used_tokens = provider_total_tokens
        usage_source = "provider_reported"
    percentage = max(0, min(100, round((used_tokens / max_tokens) * 100)))
    return {
        "percentage": percentage,
        "used_tokens": used_tokens,
        "max_tokens": max_tokens,
        "rolling_summary": rolling_summary,
        "recent_message_count": len(recent_messages),
        "memory_count": len(relevant_memory),
        "memory_items": [_serialize_memory_item(item) for item in relevant_memory],
        "usage_source": usage_source,
        "provider_input_tokens": provider_input_tokens,
        "provider_output_tokens": provider_output_tokens,
        "provider_total_tokens": provider_total_tokens,
    }


def _build_rolling_summary(messages: list[dict], *, stored_summary: str = "") -> str:
    if not messages:
        return stored_summary.strip()

    summary_lines: list[str] = []
    for message in messages[-6:]:
        role = "User" if str(message.get("role")) == "user" else "Assistant"
        text = _normalize_whitespace(str(message.get("text", "")))
        if not text:
            continue
        summary_lines.append(f"- {role}: {_truncate(text, 180)}")
    return "\n".join(summary_lines).strip()


def _latest_user_message(messages: list[dict]) -> dict | None:
    for message in reversed(messages):
        if str(message.get("role")) == "user":
            return message
    return None


def _latest_user_message_text(messages: list[dict]) -> str:
    latest = _latest_user_message(messages)
    if latest is None:
        return ""
    return str(latest.get("text", ""))


def _extract_memory_items(*, workspace_id: str, thread_id: str, source_message: dict) -> list[dict]:
    text = _normalize_whitespace(str(source_message.get("text", "")))
    if not text:
        return []

    clauses = [
        part.strip(" -")
        for part in re.split(r"[\n\r]+|(?<=[.!?\u061f])\s+", text)
        if part.strip()
    ]
    extracted: list[dict] = []
    seen_fingerprints: set[str] = set()
    for clause in clauses:
        memory_class = _classify_memory_clause(clause)
        if memory_class is None:
            continue
        normalized_clause = _normalize_whitespace(clause)
        fingerprint = hashlib.sha256(
            f"{workspace_id}:{memory_class}:{normalized_clause.casefold()}".encode("utf-8")
        ).hexdigest()
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)
        extracted.append(
            {
                "workspace_id": workspace_id,
                "thread_id": thread_id,
                "memory_class": memory_class,
                "title": _memory_title_from_clause(normalized_clause),
                "content": normalized_clause,
                "source_message_id": str(source_message["message_id"]),
                "content_fingerprint": fingerprint,
                "tags": _memory_tags(memory_class, normalized_clause),
            }
        )
        if len(extracted) >= 3:
            break
    return extracted


def _classify_memory_clause(clause: str) -> str | None:
    lowered = clause.casefold()
    if any(hint in lowered for hint in CONSTRAINT_HINTS):
        return "constraint"
    if any(hint in lowered for hint in PREFERENCE_HINTS):
        return "preference"
    if any(hint in lowered for hint in DECISION_HINTS):
        return "decision"
    if len(clause) >= 28:
        return "goal"
    return None


def _memory_title_from_clause(clause: str) -> str:
    words = clause.split()
    candidate = " ".join(words[:6]).strip(" -_:,.;!?")
    return candidate[:72] or "Conversation memory"


def _memory_tags(memory_class: str, clause: str) -> list[str]:
    tokens = _tokenize(clause)
    tags = [memory_class]
    tags.extend(token for token in sorted(tokens)[:4] if len(token) > 3)
    return tags[:5]


def _select_relevant_memory(
    memory_items: list[dict],
    *,
    current_message: str,
    thread_id: str,
    limit: int,
) -> list[dict]:
    if not memory_items:
        return []

    query_tokens = _tokenize(current_message)
    scored: list[tuple[int, datetime, dict]] = []
    for item in memory_items:
        text = f"{item.get('title', '')} {item.get('content', '')}"
        overlap = len(query_tokens & _tokenize(text))
        same_thread_bonus = 4 if str(item.get("thread_id")) == thread_id else 0
        class_bonus = 2 if str(item.get("memory_class")) in {"constraint", "decision"} else 1
        score = overlap * 6 + same_thread_bonus + class_bonus
        if score <= 0 and str(item.get("thread_id")) != thread_id:
            continue
        updated_at = item.get("updated_at")
        if not isinstance(updated_at, datetime):
            updated_at = datetime.now(UTC)
        scored.append((score, updated_at, item))

    scored.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    return [item for _, _, item in scored[:limit]]


def _serialize_memory_item(item: dict) -> dict:
    return {
        "id": str(item.get("memory_id", "")),
        "memory_class": str(item.get("memory_class", "")),
        "title": str(item.get("title", "")),
        "content": str(item.get("content", "")),
        "updated_at": item.get("updated_at"),
    }


def _estimate_text_tokens(text: str) -> int:
    normalized = _normalize_whitespace(text)
    if not normalized:
        return 0
    char_count = len(normalized)
    word_count = len(normalized.split())
    return max(1, round(char_count / 4), round(word_count * 1.35))


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z0-9_]+|[\u0600-\u06FF]{2,}", text.casefold())
        if len(token) >= 2
    }


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split()).strip()


def _truncate(text: str, length: int) -> str:
    if len(text) <= length:
        return text
    return text[: length - 1].rstrip() + "..."


def _coerce_optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None
