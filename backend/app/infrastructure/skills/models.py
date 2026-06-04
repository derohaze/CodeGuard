from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Skill:
    name: str
    description: str
    tools: list[str] = field(default_factory=list)
    disable_model_invocation: bool = False
    path: str = ""
    body: str = ""

    def materialize_body(self) -> str:
        body = self.body.replace("${SKILL_DIR}", "/".join(self.path.split("/")[:-1]))
        return f"# Skill: {self.name}\n\n{body}"
