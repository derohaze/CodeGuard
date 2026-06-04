from __future__ import annotations

import os


def skill_discovery_directories(
    configured_dirs: list[str] | None = None,
    base_dir: str | None = None,
    home_dir: str | None = None,
) -> list[str]:
    cwd = base_dir or os.getcwd()
    home = home_dir or os.path.expanduser("~")
    dirs: list[str] = [
        os.path.join(cwd, "skills"),
        os.path.join(cwd, ".aegix", "skills"),
        os.path.join(home, ".aegix", "builtin-skills"),
        os.path.join(home, ".aegix", "skills"),
    ]
    if configured_dirs:
        dirs.extend(os.path.abspath(d) for d in configured_dirs)
    return dirs


def builtin_skills_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "skills")
