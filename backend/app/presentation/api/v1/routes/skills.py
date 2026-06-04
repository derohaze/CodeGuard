from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.infrastructure.skills.registry import SkillRegistry

router = APIRouter(tags=["skills"])

_registry: SkillRegistry | None = None


def init_skills(registry: SkillRegistry) -> None:
    global _registry
    _registry = registry


def get_registry() -> SkillRegistry:
    if _registry is None:
        raise RuntimeError("skills not initialized")
    return _registry


class SkillResponse(BaseModel):
    name: str
    description: str
    tools: list[str]
    disabled: bool
    disable_model_invocation: bool


class SkillBodyResponse(BaseModel):
    name: str
    body: str


class SkillToggleRequest(BaseModel):
    name: str
    enabled: bool


@router.get("/skills", response_model=list[SkillResponse])
async def list_skills(show_disabled: bool = False):
    reg = get_registry()
    skills = reg.list() if show_disabled else reg.list_enabled()
    return [
        SkillResponse(
            name=s.name,
            description=s.description,
            tools=s.tools,
            disabled=reg.is_disabled(s.name),
            disable_model_invocation=s.disable_model_invocation,
        )
        for s in skills
    ]


@router.get("/skills/{name}", response_model=SkillBodyResponse)
async def get_skill(name: str):
    reg = get_registry()
    skill = reg.get(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"skill '{name}' not found")
    return SkillBodyResponse(name=skill.name, body=skill.materialize_body())


@router.post("/skills/toggle")
async def toggle_skill(req: SkillToggleRequest):
    reg = get_registry()
    if not reg.has(req.name):
        raise HTTPException(status_code=404, detail=f"skill '{req.name}' not found")
    changed = reg.set_disabled(req.name, not req.enabled)
    return {"name": req.name, "enabled": req.enabled, "changed": changed}


@router.post("/skills/reload")
async def reload_skills():
    reg = get_registry()
    reg.clear()
    reg.load_builtin_skills()
    return {"status": "reloaded", "count": len(reg.list())}
