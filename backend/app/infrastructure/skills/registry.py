from __future__ import annotations

import os
import re
import yaml

from app.infrastructure.skills.models import Skill


NAME_RE = re.compile(r"^[a-z0-9-]+$")
MAX_DESCRIPTION = 1024


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._disabled: set[str] = set()

    def add(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def has(self, name: str) -> bool:
        return name in self._skills

    def list(self) -> list[Skill]:
        return sorted(self._skills.values(), key=lambda s: s.name)

    def list_enabled(self) -> list[Skill]:
        return [s for s in self.list() if s.name not in self._disabled]

    def set_disabled_names(self, names: list[str]) -> None:
        self._disabled = set(names)

    def disabled_names(self) -> list[str]:
        return sorted(self._disabled)

    def is_disabled(self, name: str) -> bool:
        return name in self._disabled

    def clear(self) -> None:
        self._skills.clear()

    def set_disabled(self, name: str, on: bool) -> bool:
        was = name in self._disabled
        if on and not was:
            self._disabled.add(name)
            return True
        if not on and was:
            self._disabled.discard(name)
            return True
        return False

    def load_dir(self, directory: str) -> None:
        if not os.path.isdir(directory):
            return
        for entry in sorted(os.listdir(directory)):
            if entry.startswith(".") or entry.startswith("_"):
                continue
            sub = os.path.join(directory, entry)
            if not os.path.isdir(sub):
                continue
            skill_file = os.path.join(sub, "SKILL.md")
            if not os.path.isfile(skill_file):
                continue
            try:
                self.add(parse_skill(skill_file))
            except Exception as exc:
                import sys
                print(f"[skills] skip {skill_file}: {exc}", file=sys.stderr)

    def load_builtin_skills(self) -> None:
        builtin_dir = os.path.join(os.path.dirname(__file__), "skills")
        self.load_dir(builtin_dir)


def parse_skill(path: str) -> Skill:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    parts = content.split("---", 2)
    if len(parts) < 3:
        return Skill(
            name=os.path.basename(os.path.dirname(path)),
            path=path,
            body=content,
        )

    frontmatter = yaml.safe_load(parts[1]) or {}
    body = parts[2].lstrip("\n")

    name = frontmatter.get("name") or os.path.basename(os.path.dirname(path))
    description = frontmatter.get("description", "")
    disable_model_invocation = frontmatter.get(
        "disable-model-invocation",
        frontmatter.get("disableModelInvocation", False),
    )
    tools_raw = frontmatter.get("allowed-tools") or frontmatter.get("allowedTools") or frontmatter.get("tools") or []
    tools = [t for t in tools_raw if isinstance(t, str)]

    return Skill(
        name=name,
        description=description,
        tools=tools,
        disable_model_invocation=bool(disable_model_invocation),
        path=path,
        body=body,
    )


def validate_skill(skill: Skill, known_tools: set[str]) -> list[str]:
    errs: list[str] = []
    directory = os.path.basename(os.path.dirname(skill.path))
    if not skill.name:
        errs.append("missing `name`")
    elif not NAME_RE.match(skill.name):
        errs.append(f'name "{skill.name}" must be lowercase-kebab ([a-z0-9-])')
    elif skill.name != directory:
        errs.append(f'name "{skill.name}" does not match its directory "{directory}"')
    if not skill.description:
        errs.append("missing `description`")
    elif len(skill.description) > MAX_DESCRIPTION:
        errs.append(f"description is {len(skill.description)} chars (max {MAX_DESCRIPTION})")
    for t in skill.tools:
        if t not in known_tools:
            errs.append(f'allowed-tools entry "{t}" is not a known tool')
    return errs
