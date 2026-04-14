import asyncio
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.builder_agent.provider import BuilderProviderReply, BuilderProviderUsage
from app.builder_agent.service import BuilderAgentService, _title_from_message


class InMemoryBuilderRepository:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.workspace_id = str(uuid4())
        self.workspaces = {
            self.workspace_id: {
                "workspace_id": self.workspace_id,
                "path": "D:/repo/demo",
                "label": "demo",
                "archived": False,
                "created_at": now,
                "updated_at": now,
            }
        }
        self.threads: dict[str, dict] = {}
        self.messages: dict[str, list[dict]] = {}
        self.thread_contexts: dict[str, dict] = {}
        self.memory_items: dict[str, dict] = {}

    async def list_workspaces(self):
        payload: list[dict] = []
        for workspace in self.workspaces.values():
            if workspace.get("archived"):
                continue
            threads = [
                {
                    "id": item["thread_id"],
                    "title": item["title"],
                    "updated_at": item["updated_at"],
                }
                for item in self.threads.values()
                if item["workspace_id"] == workspace["workspace_id"] and not item.get("archived")
            ]
            payload.append(
                {
                    "id": workspace["workspace_id"],
                    "label": workspace["label"],
                    "path": workspace["path"],
                    "updated_at": workspace["updated_at"],
                    "threads": threads,
                }
            )
        return payload

    async def get_workspace(self, workspace_id: str):
        workspace = self.workspaces.get(workspace_id)
        if workspace and not workspace.get("archived"):
            return workspace
        return None

    async def get_workspace_by_path(self, path: str):
        for workspace in self.workspaces.values():
            if workspace["path"] == path and not workspace.get("archived"):
                return workspace
        return None

    async def create_workspace(self, path: str, label: str):
        now = datetime.now(UTC)
        workspace_id = str(uuid4())
        doc = {
            "workspace_id": workspace_id,
            "path": path,
            "label": label,
            "archived": False,
            "created_at": now,
            "updated_at": now,
        }
        self.workspaces[workspace_id] = doc
        return doc

    async def update_workspace_label(self, workspace_id: str, label: str):
        workspace = self.workspaces.get(workspace_id)
        if workspace is None:
            return None
        workspace["label"] = label
        workspace["updated_at"] = datetime.now(UTC)
        return workspace

    async def delete_workspace(self, workspace_id: str):
        self.workspaces.pop(workspace_id, None)
        thread_ids = [item["thread_id"] for item in self.threads.values() if item["workspace_id"] == workspace_id]
        for thread_id in thread_ids:
            self.threads.pop(thread_id, None)
            self.messages.pop(thread_id, None)

    async def create_thread(self, workspace_id: str, title: str):
        now = datetime.now(UTC)
        thread_id = str(uuid4())
        doc = {
            "thread_id": thread_id,
            "workspace_id": workspace_id,
            "title": title,
            "archived": False,
            "created_at": now,
            "updated_at": now,
        }
        self.threads[thread_id] = doc
        return doc

    async def get_thread(self, thread_id: str):
        thread = self.threads.get(thread_id)
        if thread and not thread.get("archived"):
            return thread
        return None

    async def rename_thread(self, thread_id: str, title: str):
        thread = await self.get_thread(thread_id)
        if thread is None:
            return None
        thread["title"] = title
        thread["updated_at"] = datetime.now(UTC)
        return thread

    async def archive_thread(self, thread_id: str):
        thread = self.threads.get(thread_id)
        if thread is None or thread.get("archived"):
            return None
        thread["archived"] = True
        thread["updated_at"] = datetime.now(UTC)
        return thread

    async def archive_workspace_threads(self, workspace_id: str):
        count = 0
        for thread in self.threads.values():
            if thread["workspace_id"] == workspace_id and not thread.get("archived"):
                thread["archived"] = True
                thread["updated_at"] = datetime.now(UTC)
                count += 1
        return count

    async def delete_thread(self, thread_id: str):
        self.threads.pop(thread_id, None)
        self.messages.pop(thread_id, None)

    async def add_message(self, *, workspace_id: str, thread_id: str, role: str, text: str, model: str | None = None):
        now = datetime.now(UTC)
        message = {
            "message_id": str(uuid4()),
            "workspace_id": workspace_id,
            "thread_id": thread_id,
            "role": role,
            "text": text,
            "model": model,
            "created_at": now,
        }
        self.messages.setdefault(thread_id, []).append(message)
        thread = self.threads[thread_id]
        thread["updated_at"] = now
        self.workspaces[workspace_id]["updated_at"] = now
        return message

    async def list_recent_messages(self, thread_id: str, limit: int):
        return self.messages.get(thread_id, [])[-limit:]

    async def list_messages(self, thread_id: str):
        return list(self.messages.get(thread_id, []))

    async def get_thread_context(self, thread_id: str):
        return self.thread_contexts.get(thread_id)

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
        last_message_at,
        usage_source: str = "estimated",
        provider_input_tokens: int | None = None,
        provider_output_tokens: int | None = None,
        provider_total_tokens: int | None = None,
    ):
        document = {
            "thread_id": thread_id,
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
            "updated_at": datetime.now(UTC),
        }
        self.thread_contexts[thread_id] = document
        return document

    async def list_memory_items(self, workspace_id: str, *, limit: int = 100):
        items = [item for item in self.memory_items.values() if item["workspace_id"] == workspace_id]
        items.sort(key=lambda item: item["updated_at"], reverse=True)
        return items[:limit]

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
    ):
        now = datetime.now(UTC)
        existing = self.memory_items.get(content_fingerprint)
        document = {
            "memory_id": existing["memory_id"] if existing else str(uuid4()),
            "workspace_id": workspace_id,
            "thread_id": thread_id,
            "memory_class": memory_class,
            "title": title,
            "content": content,
            "source_message_id": source_message_id,
            "content_fingerprint": content_fingerprint,
            "tags": tags,
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
        }
        self.memory_items[content_fingerprint] = document
        return document

    async def get_thread_detail(self, thread_id: str):
        thread = await self.get_thread(thread_id)
        if thread is None:
            return None
        return {
            "id": thread["thread_id"],
            "workspace_id": thread["workspace_id"],
            "title": thread["title"],
            "updated_at": thread["updated_at"],
            "messages": [
                {
                    "id": item["message_id"],
                    "role": item["role"],
                    "text": item["text"],
                    "created_at": item["created_at"],
                    "model": item["model"],
                }
                for item in self.messages.get(thread_id, [])
            ],
        }


class StubBuilderProvider:
    def __init__(self) -> None:
        self.last_messages: list[dict] = []

    async def generate_reply(self, messages):
        assert messages
        self.last_messages = messages
        return BuilderProviderReply(
            text="ack",
            model="route/glm-5.1",
            usage=BuilderProviderUsage(
                input_tokens=2140,
                output_tokens=140,
                total_tokens=2280,
            ),
        )

    async def generate_reply_stream(self, messages):
        assert messages
        self.last_messages = messages
        yield {"type": "meta", "model": "route/glm-5.1"}
        yield {"type": "usage", "input_tokens": 1980, "output_tokens": 120, "total_tokens": 2100}
        yield {"type": "reasoning", "text": "Planning the answer"}
        yield {"type": "token", "text": "a"}
        yield {"type": "token", "text": " ck"}


class BuilderAgentServiceTests(unittest.TestCase):
    def test_send_message_creates_thread_and_persists_history(self):
        repository = InMemoryBuilderRepository()
        provider = StubBuilderProvider()
        service = BuilderAgentService(repository=repository, provider=provider)

        result = asyncio.run(
            service.send_message(
                workspace_id=repository.workspace_id,
                thread_id=None,
                message="hello world",
                permission_mode="full-access",
                plan_mode=False,
                response_speed="normal",
            )
        )

        self.assertEqual(result["assistant_message"]["text"], "ack")
        self.assertEqual(result["assistant_message"]["role"], "assistant")
        self.assertEqual(len(result["thread"]["messages"]), 2)
        self.assertEqual(result["thread"]["messages"][0]["role"], "user")
        self.assertEqual(result["thread"]["messages"][1]["role"], "assistant")
        self.assertIsNotNone(result["thread"]["context_state"])
        self.assertEqual(provider.last_messages[0]["role"], "system")
        self.assertIn("Source priority", provider.last_messages[0]["content"])
        self.assertEqual(result["thread"]["context_state"]["used_tokens"], 2140)
        self.assertEqual(repository.thread_contexts[result["thread"]["id"]]["usage_source"], "provider_reported")

    def test_create_workspace_reuses_existing_path(self):
        repository = InMemoryBuilderRepository()
        service = BuilderAgentService(repository=repository, provider=StubBuilderProvider())

        first = asyncio.run(service.create_workspace(path="D:/repo/new", label="new"))
        second = asyncio.run(service.create_workspace(path="D:/repo/new", label="renamed"))

        self.assertEqual(first["path"], second["path"])
        self.assertEqual(first["id"], second["id"])

    def test_send_message_stream_persists_final_assistant_message(self):
        repository = InMemoryBuilderRepository()
        provider = StubBuilderProvider()
        service = BuilderAgentService(repository=repository, provider=provider)

        async def run_case():
            events = []
            async for event in service.send_message_stream(
                workspace_id=repository.workspace_id,
                thread_id=None,
                message="hello world",
                permission_mode="full-access",
                plan_mode=False,
                response_speed="normal",
            ):
                events.append(event)
            return events

        events = asyncio.run(run_case())
        event_types = [item["type"] for item in events]
        self.assertIn("ack", event_types)
        self.assertIn("reasoning", event_types)
        self.assertIn("token", event_types)
        self.assertIn("done", event_types)
        self.assertIn("context_state", events[0])
        done_event = [item for item in events if item["type"] == "done"][0]
        self.assertEqual(done_event["assistant_message"]["text"], "a ck")
        self.assertIn("context_state", done_event["thread"])
        self.assertEqual(provider.last_messages[0]["role"], "system")
        self.assertEqual(done_event["thread"]["context_state"]["used_tokens"], 1980)

    def test_title_from_message_extracts_topic_instead_of_raw_prompt(self):
        self.assertEqual(_title_from_message("A topic about mind misery"), "Mind Misery")
        self.assertEqual(_title_from_message("موضوع عن الأمن السيبراني الحديث"), "الأمن السيبراني الحديث")

    def test_send_message_replaces_placeholder_thread_title_with_topic_title(self):
        repository = InMemoryBuilderRepository()
        service = BuilderAgentService(repository=repository, provider=StubBuilderProvider())
        thread = asyncio.run(service.create_thread(repository.workspace_id))

        result = asyncio.run(
            service.send_message(
                workspace_id=repository.workspace_id,
                thread_id=thread["id"],
                message="A topic about mind misery",
                permission_mode="full-access",
                plan_mode=False,
                response_speed="normal",
            )
        )

        self.assertEqual(result["thread"]["title"], "Mind Misery")

    def test_send_message_extracts_memory_and_builds_summary_for_follow_up_turn(self):
        repository = InMemoryBuilderRepository()
        provider = StubBuilderProvider()
        service = BuilderAgentService(repository=repository, provider=provider)

        first = asyncio.run(
            service.send_message(
                workspace_id=repository.workspace_id,
                thread_id=None,
                message="Please keep the replies concise and do not remove the current architecture.",
                permission_mode="full-access",
                plan_mode=False,
                response_speed="normal",
            )
        )
        thread_id = first["thread"]["id"]

        for index in range(4):
            asyncio.run(
                service.send_message(
                    workspace_id=repository.workspace_id,
                    thread_id=thread_id,
                    message=f"Continue step {index + 1} for the backend cleanup.",
                    permission_mode="full-access",
                    plan_mode=False,
                    response_speed="normal",
                )
            )

        second = asyncio.run(
            service.send_message(
                workspace_id=repository.workspace_id,
                thread_id=thread_id,
                message="Continue with the backend cleanup.",
                permission_mode="full-access",
                plan_mode=False,
                response_speed="normal",
            )
        )

        context_state = second["thread"]["context_state"]
        self.assertGreaterEqual(context_state["memory_count"], 1)
        self.assertTrue(any(item["memory_class"] == "constraint" for item in context_state["memory_items"]))
        self.assertIn("Rolling summary", provider.last_messages[0]["content"])
        self.assertIn("Retrieved memory", provider.last_messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
