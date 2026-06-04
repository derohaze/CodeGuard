from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel


class PermissionRequest(BaseModel):
    tool: str
    summary: str
    detail: str
    bypass_yolo: bool = False
    no_session_cache: bool = False


Decision = Literal["allow-once", "allow-session", "deny"]
Decision = str  # one of the literals above


class Prompter:
    async def ask(self, request: PermissionRequest) -> Decision:
        raise NotImplementedError

from typing import Literal
