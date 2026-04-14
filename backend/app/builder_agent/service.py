from __future__ import annotations

from collections.abc import AsyncIterator
import re

from app.builder_agent.context import BuilderContextManager, BuilderTokenUsage, PreparedBuilderContext
from app.builder_agent.repository import BuilderAgentRepository
from app.core.config import get_settings
from app.core.exceptions import CodeGuardError


class BuilderAgentService:
    def __init__(
        self,
        repository: BuilderAgentRepository,
        provider,
        context_manager: BuilderContextManager | None = None,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.context_manager = context_manager or BuilderContextManager(repository)

    async def list_workspaces(self) -> list[dict]:
        return await self.repository.list_workspaces()

    async def create_workspace(self, *, path: str, label: str | None = None) -> dict:
        normalized_path = path.strip()
        if not normalized_path:
            raise CodeGuardError("Workspace path cannot be empty.")

        existing = await self.repository.get_workspace_by_path(normalized_path)
        if existing is not None:
            return {
                "id": str(existing["workspace_id"]),
                "label": str(existing.get("label", label or _label_from_path(normalized_path))),
                "path": str(existing["path"]),
                "updated_at": existing["updated_at"],
                "threads": [],
            }

        workspace = await self.repository.create_workspace(
            path=normalized_path,
            label=(label.strip() if label and label.strip() else _label_from_path(normalized_path)),
        )
        return {
            "id": str(workspace["workspace_id"]),
            "label": str(workspace["label"]),
            "path": str(workspace["path"]),
            "updated_at": workspace["updated_at"],
            "threads": [],
        }

    async def rename_workspace(self, workspace_id: str, label: str) -> dict:
        normalized_label = label.strip()
        if not normalized_label:
            raise CodeGuardError("Workspace label cannot be empty.")
        updated = await self.repository.update_workspace_label(workspace_id, normalized_label)
        if updated is None:
            raise CodeGuardError("Workspace not found.")
        return {
            "id": str(updated["workspace_id"]),
            "label": str(updated["label"]),
            "path": str(updated["path"]),
            "updated_at": updated["updated_at"],
            "threads": [],
        }

    async def delete_workspace(self, workspace_id: str) -> None:
        workspace = await self.repository.get_workspace(workspace_id)
        if workspace is None:
            raise CodeGuardError("Workspace not found.")
        await self.repository.delete_workspace(workspace_id)

    async def create_thread(self, workspace_id: str, title: str | None = None) -> dict:
        workspace = await self.repository.get_workspace(workspace_id)
        if workspace is None:
            raise CodeGuardError("Workspace not found.")

        normalized_title = title.strip() if title else ""
        thread = await self.repository.create_thread(
            workspace_id=workspace_id,
            title=normalized_title or "New chat",
        )
        detail = await self.repository.get_thread_detail(str(thread["thread_id"]))
        if detail is None:
            raise CodeGuardError("Unable to create builder thread.")
        return await self._with_context_state(detail)

    async def get_thread(self, thread_id: str) -> dict:
        detail = await self.repository.get_thread_detail(thread_id)
        if detail is None:
            raise CodeGuardError("Thread not found.")
        return await self._with_context_state(detail)

    async def rename_thread(self, thread_id: str, title: str) -> dict:
        normalized_title = title.strip()
        if not normalized_title:
            raise CodeGuardError("Thread title cannot be empty.")

        thread = await self.repository.rename_thread(thread_id, normalized_title)
        if thread is None:
            raise CodeGuardError("Thread not found.")

        detail = await self.repository.get_thread_detail(thread_id)
        if detail is None:
            raise CodeGuardError("Thread not found.")
        return await self._with_context_state(detail)

    async def delete_thread(self, thread_id: str) -> None:
        thread = await self.repository.get_thread(thread_id)
        if thread is None:
            raise CodeGuardError("Thread not found.")
        await self.repository.delete_thread(thread_id)

    async def archive_thread(self, thread_id: str) -> None:
        thread = await self.repository.archive_thread(thread_id)
        if thread is None:
            raise CodeGuardError("Thread not found.")

    async def archive_workspace_threads(self, workspace_id: str) -> int:
        workspace = await self.repository.get_workspace(workspace_id)
        if workspace is None:
            raise CodeGuardError("Workspace not found.")
        return await self.repository.archive_workspace_threads(workspace_id)

    async def send_message(
        self,
        *,
        workspace_id: str,
        thread_id: str | None,
        message: str,
        permission_mode: str,
        plan_mode: bool,
        response_speed: str,
    ) -> dict:
        normalized_workspace_id, active_thread_id, prepared_context = await self._prepare_thread_and_messages(
            workspace_id=workspace_id,
            thread_id=thread_id,
            message=message,
            permission_mode=permission_mode,
            plan_mode=plan_mode,
            response_speed=response_speed,
        )
        raw_provider_reply = await self.provider.generate_reply(prepared_context.provider_messages)
        provider_reply = _coerce_provider_reply(raw_provider_reply)
        assistant_text = provider_reply.text
        model = provider_reply.model

        assistant_message = await self.repository.add_message(
            workspace_id=normalized_workspace_id,
            thread_id=active_thread_id,
            role="assistant",
            text=assistant_text,
            model=model,
        )
        context_state = await self.context_manager.record_completion(
            workspace_id=normalized_workspace_id,
            thread_id=active_thread_id,
            permission_mode=permission_mode,
            plan_mode=plan_mode,
            provider_usage=_map_provider_usage(provider_reply.usage),
        )
        detail = await self.repository.get_thread_detail(active_thread_id)
        if detail is None:
            raise CodeGuardError("Thread not found.")

        return {
            "thread": {
                **detail,
                "context_state": context_state,
            },
            "assistant_message": {
                "id": str(assistant_message["message_id"]),
                "role": str(assistant_message["role"]),
                "text": str(assistant_message["text"]),
                "created_at": assistant_message["created_at"],
                "model": str(assistant_message["model"]) if assistant_message.get("model") else None,
            },
        }

    async def send_message_stream(
        self,
        *,
        workspace_id: str,
        thread_id: str | None,
        message: str,
        permission_mode: str,
        plan_mode: bool,
        response_speed: str,
    ) -> AsyncIterator[dict]:
        normalized_workspace_id, active_thread_id, prepared_context = await self._prepare_thread_and_messages(
            workspace_id=workspace_id,
            thread_id=thread_id,
            message=message,
            permission_mode=permission_mode,
            plan_mode=plan_mode,
            response_speed=response_speed,
        )

        accumulated: list[str] = []
        model = get_settings().builder_chat_model
        provider_usage: BuilderTokenUsage | None = None

        yield {
            "type": "ack",
            "thread_id": active_thread_id,
            "workspace_id": normalized_workspace_id,
            "context_state": prepared_context.context_state,
        }
        async for chunk in self.provider.generate_reply_stream(prepared_context.provider_messages):
            chunk_type = str(chunk.get("type", ""))
            if chunk_type == "token":
                text = str(chunk.get("text", ""))
                if not text:
                    continue
                accumulated.append(text)
                yield {
                    "type": "token",
                    "text": text,
                }
            elif chunk_type == "reasoning":
                text = str(chunk.get("text", "")).strip()
                if not text:
                    continue
                yield {
                    "type": "reasoning",
                    "text": text,
                }
            elif chunk_type == "meta":
                next_model = str(chunk.get("model", "")).strip()
                if next_model:
                    model = next_model
            elif chunk_type == "usage":
                provider_usage = BuilderTokenUsage(
                    input_tokens=_safe_optional_int(chunk.get("input_tokens")),
                    output_tokens=_safe_optional_int(chunk.get("output_tokens")),
                    total_tokens=_safe_optional_int(chunk.get("total_tokens")),
                )

        assistant_text = "".join(accumulated).strip()
        if not assistant_text:
            raise CodeGuardError("Builder provider returned empty message content.")

        assistant_message = await self.repository.add_message(
            workspace_id=normalized_workspace_id,
            thread_id=active_thread_id,
            role="assistant",
            text=assistant_text,
            model=model,
        )
        context_state = await self.context_manager.record_completion(
            workspace_id=normalized_workspace_id,
            thread_id=active_thread_id,
            permission_mode=permission_mode,
            plan_mode=plan_mode,
            provider_usage=provider_usage,
        )
        detail = await self.repository.get_thread_detail(active_thread_id)
        if detail is None:
            raise CodeGuardError("Thread not found.")

        yield {
            "type": "done",
            "thread": {
                **detail,
                "context_state": context_state,
            },
            "assistant_message": {
                "id": str(assistant_message["message_id"]),
                "role": str(assistant_message["role"]),
                "text": str(assistant_message["text"]),
                "created_at": assistant_message["created_at"],
                "model": str(assistant_message["model"]) if assistant_message.get("model") else None,
            },
        }

    async def _prepare_thread_and_messages(
        self,
        *,
        workspace_id: str,
        thread_id: str | None,
        message: str,
        permission_mode: str,
        plan_mode: bool,
        response_speed: str,
    ) -> tuple[str, str, PreparedBuilderContext]:
        normalized_workspace_id = workspace_id.strip()
        if not normalized_workspace_id:
            raise CodeGuardError("workspace_id is required.")

        normalized_message = message.strip()
        if not normalized_message:
            raise CodeGuardError("Message cannot be empty.")

        workspace = await self.repository.get_workspace(normalized_workspace_id)
        if workspace is None:
            raise CodeGuardError("Workspace not found.")

        active_thread_id = (thread_id or "").strip() or None
        if active_thread_id is None:
            created = await self.repository.create_thread(
                workspace_id=normalized_workspace_id,
                title=_title_from_message(normalized_message),
            )
            active_thread_id = str(created["thread_id"])
        else:
            existing_thread = await self.repository.get_thread(active_thread_id)
            if existing_thread is None or str(existing_thread["workspace_id"]) != normalized_workspace_id:
                raise CodeGuardError("Thread not found for this workspace.")
            derived_title = _title_from_message(normalized_message)
            existing_title = str(existing_thread.get("title", "")).strip()
            if _should_replace_thread_title(existing_title, normalized_message):
                await self.repository.rename_thread(active_thread_id, derived_title)

        await self.repository.add_message(
            workspace_id=normalized_workspace_id,
            thread_id=active_thread_id,
            role="user",
            text=normalized_message,
        )
        prepared_context = await self.context_manager.prepare_context(
            workspace_id=normalized_workspace_id,
            thread_id=active_thread_id,
            permission_mode=permission_mode,
            plan_mode=plan_mode,
            response_speed=response_speed,
        )
        return normalized_workspace_id, active_thread_id, prepared_context

    async def _with_context_state(self, detail: dict) -> dict:
        context_state = await self.context_manager.get_thread_context_state(
            workspace_id=str(detail["workspace_id"]),
            thread_id=str(detail["id"]),
        )
        return {
            **detail,
            "context_state": context_state,
        }


def _label_from_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if not parts:
        return "workspace"
    return parts[-1]


def _title_from_message(message: str) -> str:
    cleaned = " ".join(message.split())
    if not cleaned:
        return "New chat"
    normalized = _strip_title_prefixes(cleaned)
    normalized = _strip_leading_punctuation(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" -_:,.;!?")
    if not normalized:
        normalized = cleaned

    words = normalized.split()
    candidate = " ".join(words[:6]).strip()
    if len(candidate) < 6 and len(words) > 6:
        candidate = " ".join(words[:8]).strip()
    if len(candidate) < 4:
        candidate = normalized

    candidate = _sentence_case_title(candidate[:72].strip())
    return candidate or "New chat"


def _should_replace_thread_title(existing_title: str, message: str) -> bool:
    if not existing_title:
        return True

    normalized_title = " ".join(existing_title.split()).strip().casefold()
    normalized_message = " ".join(message.split()).strip()
    if not normalized_message:
        return normalized_title in {"", "new chat"}

    normalized_message_casefold = normalized_message.casefold()
    if normalized_title == "new chat":
        return True
    if normalized_title == normalized_message_casefold:
        return True
    if normalized_title == normalized_message[:96].strip().casefold():
        return True
    return False


def _strip_title_prefixes(text: str) -> str:
    prefixes = (
        "write me ",
        "write ",
        "give me ",
        "make me ",
        "create ",
        "generate ",
        "a topic about ",
        "topic about ",
        "an article about ",
        "article about ",
        "essay about ",
        "doc about ",
        "documentation about ",
        "explain ",
        "tell me about ",
        "\u0645\u0648\u0636\u0648\u0639 \u0639\u0646 ",
        "\u0627\u0643\u062a\u0628 \u0639\u0646 ",
        "\u0627\u0643\u062a\u0628\u0644\u064a \u0639\u0646 ",
        "\u0627\u0639\u0645\u0644 \u0645\u0648\u0636\u0648\u0639 \u0639\u0646 ",
        "\u0639\u0627\u064a\u0632 \u0645\u0648\u0636\u0648\u0639 \u0639\u0646 ",
        "\u0639\u0627\u064a\u0632 \u0639\u0646\u0648\u0627\u0646 \u0639\u0646 ",
        "\u0645\u0642\u0627\u0644 \u0639\u0646 ",
        "\u0634\u0631\u062d \u0639\u0646 ",
    )

    lowered = text.casefold()
    for prefix in prefixes:
        if lowered.startswith(prefix.casefold()):
            return text[len(prefix):].strip()
    return text


def _strip_leading_punctuation(text: str) -> str:
    return text.lstrip(" -_:,.;!?[](){}\"'")


def _sentence_case_title(text: str) -> str:
    parts = [part for part in re.split(r"(\s+)", text) if part]
    transformed: list[str] = []
    for part in parts:
        if part.isspace():
            transformed.append(part)
            continue
        if re.search(r"[A-Za-z]", part):
            transformed.append(part[:1].upper() + part[1:])
        else:
            transformed.append(part)
    return "".join(transformed)


def _map_provider_usage(value) -> BuilderTokenUsage | None:
    if value is None:
        return None
    return BuilderTokenUsage(
        input_tokens=_safe_optional_int(getattr(value, "input_tokens", None)),
        output_tokens=_safe_optional_int(getattr(value, "output_tokens", None)),
        total_tokens=_safe_optional_int(getattr(value, "total_tokens", None)),
    )


def _coerce_provider_reply(value) -> object:
    if hasattr(value, "text") and hasattr(value, "model"):
        return value
    if isinstance(value, tuple) and len(value) >= 2:
        text, model = value[0], value[1]
        usage = value[2] if len(value) > 2 else None

        class _LegacyProviderReply:
            def __init__(self, text_value, model_value, usage_value) -> None:
                self.text = str(text_value)
                self.model = str(model_value)
                self.usage = usage_value

        return _LegacyProviderReply(text, model, usage)
    raise CodeGuardError("Builder provider returned an unsupported reply payload.")


def _safe_optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None
