from __future__ import annotations

from collections.abc import AsyncIterator

from app.builder_agent.repository import BuilderAgentRepository
from app.core.config import get_settings
from app.core.exceptions import CodeGuardError


class BuilderAgentService:
    def __init__(
        self,
        repository: BuilderAgentRepository,
        provider,
    ) -> None:
        self.repository = repository
        self.provider = provider

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
        return detail

    async def get_thread(self, thread_id: str) -> dict:
        detail = await self.repository.get_thread_detail(thread_id)
        if detail is None:
            raise CodeGuardError("Thread not found.")
        return detail

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
        return detail

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
        _ = permission_mode
        _ = plan_mode
        _ = response_speed

        normalized_workspace_id, active_thread_id, provider_messages = await self._prepare_thread_and_messages(
            workspace_id=workspace_id,
            thread_id=thread_id,
            message=message,
        )
        assistant_text, model = await self.provider.generate_reply(provider_messages)

        assistant_message = await self.repository.add_message(
            workspace_id=normalized_workspace_id,
            thread_id=active_thread_id,
            role="assistant",
            text=assistant_text,
            model=model,
        )

        detail = await self.repository.get_thread_detail(active_thread_id)
        if detail is None:
            raise CodeGuardError("Thread not found.")

        return {
            "thread": detail,
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
        _ = permission_mode
        _ = plan_mode
        _ = response_speed

        normalized_workspace_id, active_thread_id, provider_messages = await self._prepare_thread_and_messages(
            workspace_id=workspace_id,
            thread_id=thread_id,
            message=message,
        )

        accumulated: list[str] = []
        model = get_settings().builder_chat_model

        yield {
            "type": "ack",
            "thread_id": active_thread_id,
            "workspace_id": normalized_workspace_id,
        }
        async for chunk in self.provider.generate_reply_stream(provider_messages):
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
        detail = await self.repository.get_thread_detail(active_thread_id)
        if detail is None:
            raise CodeGuardError("Thread not found.")

        yield {
            "type": "done",
            "thread": detail,
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
    ) -> tuple[str, str, list[dict[str, str]]]:
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

        await self.repository.add_message(
            workspace_id=normalized_workspace_id,
            thread_id=active_thread_id,
            role="user",
            text=normalized_message,
        )

        settings = get_settings()
        recent = await self.repository.list_recent_messages(
            active_thread_id,
            limit=settings.builder_chat_max_history_messages,
        )
        provider_messages = [
            {
                "role": str(item["role"]),
                "content": str(item["text"]),
            }
            for item in recent
            if str(item.get("role")) in {"user", "assistant"}
        ]
        return normalized_workspace_id, active_thread_id, provider_messages


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
    return cleaned[:96]
