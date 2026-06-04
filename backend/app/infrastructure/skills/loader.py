from __future__ import annotations

from app.infrastructure.skills.models import Skill
from app.infrastructure.skills.registry import SkillRegistry


class LoadSkillTool:
    def __init__(self, registry: SkillRegistry):
        self._registry = registry

    async def execute(self, name: str) -> str:
        if not name:
            raise ValueError("name is required")
        skill = self._registry.get(name)
        if not skill:
            enabled_names = [
                s.name
                for s in self._registry.list_enabled()
                if not s.disable_model_invocation
            ]
            raise ValueError(
                f'unknown skill "{name}". Available: {", ".join(enabled_names)}'
            )
        if self._registry.is_disabled(name):
            raise ValueError(
                f'skill "{name}" is disabled. Enable it first.'
            )
        if skill.disable_model_invocation:
            raise ValueError(
                f'skill "{name}" is marked disable_model_invocation. Only users can load it.'
            )
        return skill.materialize_body()
