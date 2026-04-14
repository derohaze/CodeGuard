from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.builder_agent.contracts import (
    BuilderThreadResponse,
    BuilderWorkspaceResponse,
    BuilderWorkspacesResponse,
    CreateBuilderThreadRequest,
    CreateBuilderWorkspaceRequest,
    RenameBuilderThreadRequest,
    RenameBuilderWorkspaceRequest,
    SendBuilderMessageRequest,
    SendBuilderMessageResponse,
)
from app.builder_agent.service import BuilderAgentService
from app.core.exceptions import KhwarizmError
from app.presentation.api.v1.routes.dependencies import get_builder_agent_service


router = APIRouter()
logger = logging.getLogger("khwarizm.builder")


@router.get("/builder/workspaces", response_model=BuilderWorkspacesResponse)
async def list_builder_workspaces(
    service: BuilderAgentService = Depends(get_builder_agent_service),
):
    items = await service.list_workspaces()
    return BuilderWorkspacesResponse(items=items)


@router.post("/builder/workspaces", response_model=BuilderWorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_builder_workspace(
    payload: CreateBuilderWorkspaceRequest,
    service: BuilderAgentService = Depends(get_builder_agent_service),
):
    return await service.create_workspace(path=payload.path, label=payload.label)


@router.patch("/builder/workspaces/{workspace_id}", response_model=BuilderWorkspaceResponse)
async def rename_builder_workspace(
    workspace_id: str,
    payload: RenameBuilderWorkspaceRequest,
    service: BuilderAgentService = Depends(get_builder_agent_service),
):
    return await service.rename_workspace(workspace_id=workspace_id, label=payload.label)


@router.delete("/builder/workspaces/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_builder_workspace(
    workspace_id: str,
    service: BuilderAgentService = Depends(get_builder_agent_service),
):
    await service.delete_workspace(workspace_id)
    return None


@router.post("/builder/workspaces/{workspace_id}/threads", response_model=BuilderThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_builder_thread(
    workspace_id: str,
    payload: CreateBuilderThreadRequest,
    service: BuilderAgentService = Depends(get_builder_agent_service),
):
    return await service.create_thread(workspace_id, title=payload.title)


@router.post("/builder/workspaces/{workspace_id}/threads/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_builder_workspace_threads(
    workspace_id: str,
    service: BuilderAgentService = Depends(get_builder_agent_service),
):
    await service.archive_workspace_threads(workspace_id)
    return None


@router.get("/builder/threads/{thread_id}", response_model=BuilderThreadResponse)
async def get_builder_thread(
    thread_id: str,
    service: BuilderAgentService = Depends(get_builder_agent_service),
):
    return await service.get_thread(thread_id)


@router.patch("/builder/threads/{thread_id}", response_model=BuilderThreadResponse)
async def rename_builder_thread(
    thread_id: str,
    payload: RenameBuilderThreadRequest,
    service: BuilderAgentService = Depends(get_builder_agent_service),
):
    return await service.rename_thread(thread_id=thread_id, title=payload.title)


@router.delete("/builder/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_builder_thread(
    thread_id: str,
    service: BuilderAgentService = Depends(get_builder_agent_service),
):
    await service.delete_thread(thread_id)
    return None


@router.post("/builder/threads/{thread_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_builder_thread(
    thread_id: str,
    service: BuilderAgentService = Depends(get_builder_agent_service),
):
    await service.archive_thread(thread_id)
    return None


@router.post("/builder/chat/messages", response_model=SendBuilderMessageResponse)
async def send_builder_message(
    payload: SendBuilderMessageRequest,
    service: BuilderAgentService = Depends(get_builder_agent_service),
):
    logger.info("Builder chat request started", extra={"workspace_id": payload.workspace_id, "thread_id": payload.thread_id})
    return await service.send_message(
        workspace_id=payload.workspace_id,
        thread_id=payload.thread_id,
        message=payload.message,
        permission_mode=payload.permission_mode,
        plan_mode=payload.plan_mode,
        response_speed=payload.response_speed,
    )


@router.post("/builder/chat/messages/stream")
async def send_builder_message_stream(
    payload: SendBuilderMessageRequest,
    service: BuilderAgentService = Depends(get_builder_agent_service),
):
    logger.info("Builder chat stream started", extra={"workspace_id": payload.workspace_id, "thread_id": payload.thread_id})

    async def event_stream():
        try:
            async for event in service.send_message_stream(
                workspace_id=payload.workspace_id,
                thread_id=payload.thread_id,
                message=payload.message,
                permission_mode=payload.permission_mode,
                plan_mode=payload.plan_mode,
                response_speed=payload.response_speed,
            ):
                yield _serialize_sse(str(event.get("type", "message")), event)
        except KhwarizmError as exc:
            yield _serialize_sse("error", {"message": str(exc)})
        except Exception:
            yield _serialize_sse("error", {"message": "An unexpected server error occurred."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _serialize_sse(event_name: str, data: dict) -> str:
    encoded = json.dumps(jsonable_encoder(data), ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {encoded}\n\n"
