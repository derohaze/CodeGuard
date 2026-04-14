from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pymongo import ReturnDocument

from app.infrastructure.database.collections import (
    BUILDER_MEMORY_ITEMS_COLLECTION,
    BUILDER_MESSAGES_COLLECTION,
    BUILDER_THREAD_CONTEXTS_COLLECTION,
    BUILDER_THREADS_COLLECTION,
    BUILDER_WORKSPACES_COLLECTION,
)
from app.infrastructure.database.mongo import get_database


class BuilderAgentRepository:
    def __init__(self) -> None:
        database = get_database()
        self.workspaces = database[BUILDER_WORKSPACES_COLLECTION]
        self.threads = database[BUILDER_THREADS_COLLECTION]
        self.messages = database[BUILDER_MESSAGES_COLLECTION]
        self.thread_contexts = database[BUILDER_THREAD_CONTEXTS_COLLECTION]
        self.memory_items = database[BUILDER_MEMORY_ITEMS_COLLECTION]

    async def list_workspaces(self) -> list[dict]:
        workspace_docs = await self.workspaces.find({"archived": {"$ne": True}}).sort("updated_at", -1).to_list(length=500)
        if not workspace_docs:
            return []

        workspace_ids = [str(item["workspace_id"]) for item in workspace_docs]
        thread_docs = await self.threads.find(
            {
                "workspace_id": {"$in": workspace_ids},
                "archived": {"$ne": True},
            }
        ).sort("updated_at", -1).to_list(length=5000)

        threads_by_workspace: dict[str, list[dict]] = {}
        for thread in thread_docs:
            threads_by_workspace.setdefault(str(thread["workspace_id"]), []).append(
                {
                    "id": str(thread["thread_id"]),
                    "title": str(thread.get("title", "New chat")),
                    "updated_at": thread["updated_at"],
                }
            )

        payload: list[dict] = []
        for workspace in workspace_docs:
            workspace_id = str(workspace["workspace_id"])
            payload.append(
                {
                    "id": workspace_id,
                    "label": str(workspace.get("label", workspace.get("path", workspace_id))),
                    "path": str(workspace.get("path", "")),
                    "updated_at": workspace["updated_at"],
                    "threads": threads_by_workspace.get(workspace_id, []),
                }
            )
        return payload

    async def get_workspace(self, workspace_id: str) -> dict | None:
        return await self.workspaces.find_one(
            {
                "workspace_id": workspace_id,
                "archived": {"$ne": True},
            }
        )

    async def get_workspace_by_path(self, path: str) -> dict | None:
        return await self.workspaces.find_one(
            {
                "path": path,
                "archived": {"$ne": True},
            }
        )

    async def create_workspace(self, path: str, label: str) -> dict:
        now = datetime.now(UTC)
        workspace_id = str(uuid4())
        document = {
            "workspace_id": workspace_id,
            "path": path,
            "label": label,
            "archived": False,
            "created_at": now,
            "updated_at": now,
        }
        await self.workspaces.insert_one(document)
        return document

    async def update_workspace_label(self, workspace_id: str, label: str) -> dict | None:
        now = datetime.now(UTC)
        result = await self.workspaces.find_one_and_update(
            {
                "workspace_id": workspace_id,
                "archived": {"$ne": True},
            },
            {
                "$set": {
                    "label": label,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return result

    async def delete_workspace(self, workspace_id: str) -> None:
        thread_docs = await self.threads.find(
            {
                "workspace_id": workspace_id,
            },
            {"thread_id": 1},
        ).to_list(length=5000)
        thread_ids = [str(item["thread_id"]) for item in thread_docs]
        if thread_ids:
            await self.messages.delete_many({"thread_id": {"$in": thread_ids}})
        await self.threads.delete_many({"workspace_id": workspace_id})
        await self.workspaces.delete_one({"workspace_id": workspace_id})

    async def create_thread(self, workspace_id: str, title: str) -> dict:
        now = datetime.now(UTC)
        thread_id = str(uuid4())
        document = {
            "thread_id": thread_id,
            "workspace_id": workspace_id,
            "title": title,
            "archived": False,
            "created_at": now,
            "updated_at": now,
        }
        await self.threads.insert_one(document)
        await self.workspaces.update_one(
            {"workspace_id": workspace_id},
            {"$set": {"updated_at": now}},
        )
        return document

    async def get_thread(self, thread_id: str) -> dict | None:
        return await self.threads.find_one(
            {
                "thread_id": thread_id,
                "archived": {"$ne": True},
            }
        )

    async def rename_thread(self, thread_id: str, title: str) -> dict | None:
        now = datetime.now(UTC)
        thread = await self.threads.find_one_and_update(
            {
                "thread_id": thread_id,
                "archived": {"$ne": True},
            },
            {
                "$set": {
                    "title": title,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if thread is not None:
            await self.workspaces.update_one(
                {"workspace_id": str(thread["workspace_id"])},
                {"$set": {"updated_at": now}},
            )
        return thread

    async def archive_thread(self, thread_id: str) -> dict | None:
        now = datetime.now(UTC)
        thread = await self.threads.find_one_and_update(
            {
                "thread_id": thread_id,
                "archived": {"$ne": True},
            },
            {
                "$set": {
                    "archived": True,
                    "archived_at": now,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if thread is not None:
            await self.workspaces.update_one(
                {"workspace_id": str(thread["workspace_id"])},
                {"$set": {"updated_at": now}},
            )
        return thread

    async def archive_workspace_threads(self, workspace_id: str) -> int:
        now = datetime.now(UTC)
        result = await self.threads.update_many(
            {
                "workspace_id": workspace_id,
                "archived": {"$ne": True},
            },
            {
                "$set": {
                    "archived": True,
                    "archived_at": now,
                    "updated_at": now,
                }
            },
        )
        await self.workspaces.update_one(
            {"workspace_id": workspace_id},
            {"$set": {"updated_at": now}},
        )
        return int(result.modified_count)

    async def delete_thread(self, thread_id: str) -> None:
        thread = await self.threads.find_one({"thread_id": thread_id})
        await self.messages.delete_many({"thread_id": thread_id})
        await self.threads.delete_one({"thread_id": thread_id})
        if thread is not None:
            await self.workspaces.update_one(
                {"workspace_id": str(thread["workspace_id"])},
                {"$set": {"updated_at": datetime.now(UTC)}},
            )

    async def add_message(
        self,
        *,
        workspace_id: str,
        thread_id: str,
        role: str,
        text: str,
        model: str | None = None,
    ) -> dict:
        now = datetime.now(UTC)
        message_id = str(uuid4())
        document = {
            "message_id": message_id,
            "workspace_id": workspace_id,
            "thread_id": thread_id,
            "role": role,
            "text": text,
            "model": model,
            "created_at": now,
        }
        await self.messages.insert_one(document)
        await self.threads.update_one(
            {"thread_id": thread_id},
            {"$set": {"updated_at": now}},
        )
        await self.workspaces.update_one(
            {"workspace_id": workspace_id},
            {"$set": {"updated_at": now}},
        )
        return document

    async def list_recent_messages(self, thread_id: str, limit: int) -> list[dict]:
        rows = await self.messages.find({"thread_id": thread_id}).sort("created_at", -1).limit(limit).to_list(length=limit)
        rows.reverse()
        return rows

    async def list_messages(self, thread_id: str) -> list[dict]:
        return await self.messages.find({"thread_id": thread_id}).sort("created_at", 1).to_list(length=10000)

    async def get_thread_context(self, thread_id: str) -> dict | None:
        return await self.thread_contexts.find_one({"thread_id": thread_id})

    async def upsert_thread_context(
        self,
        *,
        thread_id: str,
        workspace_id: str,
        rolling_summary: str,
        used_tokens: int,
        max_tokens: int,
        percentage: int,
        recent_message_count: int,
        memory_count: int,
        last_message_at: datetime | None,
        usage_source: str = "estimated",
        provider_input_tokens: int | None = None,
        provider_output_tokens: int | None = None,
        provider_total_tokens: int | None = None,
    ) -> dict:
        now = datetime.now(UTC)
        return await self.thread_contexts.find_one_and_update(
            {"thread_id": thread_id},
            {
                "$set": {
                    "workspace_id": workspace_id,
                    "rolling_summary": rolling_summary,
                    "used_tokens": used_tokens,
                    "max_tokens": max_tokens,
                    "percentage": percentage,
                    "recent_message_count": recent_message_count,
                    "memory_count": memory_count,
                    "last_message_at": last_message_at,
                    "usage_source": usage_source,
                    "provider_input_tokens": provider_input_tokens,
                    "provider_output_tokens": provider_output_tokens,
                    "provider_total_tokens": provider_total_tokens,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    async def list_memory_items(self, workspace_id: str, *, limit: int = 100) -> list[dict]:
        return await self.memory_items.find({"workspace_id": workspace_id}).sort("updated_at", -1).limit(limit).to_list(length=limit)

    async def upsert_memory_item(
        self,
        *,
        workspace_id: str,
        thread_id: str,
        memory_class: str,
        title: str,
        content: str,
        source_message_id: str,
        content_fingerprint: str,
        tags: list[str],
    ) -> dict:
        now = datetime.now(UTC)
        memory_id = str(uuid4())
        return await self.memory_items.find_one_and_update(
            {
                "workspace_id": workspace_id,
                "content_fingerprint": content_fingerprint,
            },
            {
                "$set": {
                    "thread_id": thread_id,
                    "memory_class": memory_class,
                    "title": title,
                    "content": content,
                    "source_message_id": source_message_id,
                    "tags": tags,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "memory_id": memory_id,
                    "workspace_id": workspace_id,
                    "created_at": now,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    async def get_thread_detail(self, thread_id: str) -> dict | None:
        thread = await self.get_thread(thread_id)
        if thread is None:
            return None

        messages = await self.messages.find({"thread_id": thread_id}).sort("created_at", 1).to_list(length=10000)
        return {
            "id": str(thread["thread_id"]),
            "workspace_id": str(thread["workspace_id"]),
            "title": str(thread.get("title", "New chat")),
            "updated_at": thread["updated_at"],
            "messages": [
                {
                    "id": str(item["message_id"]),
                    "role": str(item["role"]),
                    "text": str(item.get("text", "")),
                    "created_at": item["created_at"],
                    "model": str(item["model"]) if item.get("model") else None,
                }
                for item in messages
            ],
        }
