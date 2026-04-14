from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BuilderMessageResponse(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    text: str
    created_at: datetime
    model: str | None = None


class BuilderThreadSummaryResponse(BaseModel):
    id: str
    title: str
    updated_at: datetime


class BuilderWorkspaceResponse(BaseModel):
    id: str
    label: str
    path: str
    updated_at: datetime
    threads: list[BuilderThreadSummaryResponse]


class BuilderWorkspacesResponse(BaseModel):
    items: list[BuilderWorkspaceResponse]


class BuilderThreadResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    updated_at: datetime
    messages: list[BuilderMessageResponse]


class CreateBuilderWorkspaceRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    label: str | None = Field(default=None, min_length=1, max_length=240)


class RenameBuilderWorkspaceRequest(BaseModel):
    label: str = Field(min_length=1, max_length=240)


class CreateBuilderThreadRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)


class RenameBuilderThreadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)


class SendBuilderMessageRequest(BaseModel):
    workspace_id: str = Field(min_length=1)
    thread_id: str | None = None
    message: str = Field(min_length=1, max_length=16000)
    permission_mode: Literal["default", "full-access"] = "full-access"
    plan_mode: bool = False
    response_speed: Literal["normal", "speed"] = "normal"


class SendBuilderMessageResponse(BaseModel):
    thread: BuilderThreadResponse
    assistant_message: BuilderMessageResponse

