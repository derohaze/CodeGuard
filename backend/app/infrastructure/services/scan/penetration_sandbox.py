from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings


_DEFAULT_SANDBOX_DIRNAME = "penetration_sandboxes"
_DEFAULT_SEED_LIMIT = 8
_CODE_SUFFIXES = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rb",
    ".php",
    ".cs",
    ".kt",
    ".rs",
    ".mjs",
    ".cjs",
}


def prepare_penetration_sandbox(
    *,
    session_id: str,
    source_path: Path,
    source_root: Path,
    target_type: str,
    findings: list[dict],
) -> dict:
    settings = get_settings()
    if not settings.penetration_sandbox_enabled:
        return {
            "enabled": False,
            "mode": "disabled",
            "workspace_root": "",
            "manifest_path": "",
            "copied_files": 0,
            "skipped_files": 0,
            "truncated": False,
        }

    safe_session_id = _normalize_session_id(session_id)
    artifacts_root = Path(settings.artifacts_dir).expanduser().resolve()
    sandbox_root = artifacts_root / _DEFAULT_SANDBOX_DIRNAME / safe_session_id
    workspace_root = sandbox_root / "workspace"
    manifest_path = sandbox_root / "manifest.json"

    if sandbox_root.exists():
        shutil.rmtree(sandbox_root, ignore_errors=True)
    workspace_root.mkdir(parents=True, exist_ok=True)

    max_files = int(settings.penetration_sandbox_max_files)
    max_total_bytes = int(settings.penetration_sandbox_max_total_mb) * 1024 * 1024
    copied_paths: list[str] = []
    skipped_paths: list[str] = []
    total_bytes = 0
    truncated = False

    candidate_paths = _build_candidate_paths(
        source_path=source_path,
        source_root=source_root,
        target_type=target_type,
        findings=findings,
    )
    if not candidate_paths:
        candidate_paths = _seed_relative_files(source_root, limit=min(max_files, _DEFAULT_SEED_LIMIT))

    for rel_path in candidate_paths:
        if len(copied_paths) >= max_files:
            truncated = True
            break

        source_file = (source_root / rel_path).resolve()
        if not _is_within(source_file, source_root):
            skipped_paths.append(rel_path.as_posix())
            continue
        if not source_file.exists() or not source_file.is_file():
            skipped_paths.append(rel_path.as_posix())
            continue

        file_size = source_file.stat().st_size
        if total_bytes + file_size > max_total_bytes:
            truncated = True
            continue

        target_file = (workspace_root / rel_path).resolve()
        if not _is_within(target_file, workspace_root):
            skipped_paths.append(rel_path.as_posix())
            continue
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target_file)

        copied_paths.append(rel_path.as_posix())
        total_bytes += file_size

    manifest = {
        "session_id": safe_session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source_path),
        "source_root": str(source_root),
        "target_type": target_type,
        "sandbox_mode": "isolated_copy",
        "workspace_root": str(workspace_root),
        "copied_files": copied_paths,
        "skipped_files": skipped_paths,
        "copied_files_count": len(copied_paths),
        "skipped_files_count": len(skipped_paths),
        "max_files": max_files,
        "max_total_mb": int(settings.penetration_sandbox_max_total_mb),
        "copied_total_bytes": total_bytes,
        "truncated": truncated,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "enabled": True,
        "mode": "isolated_copy",
        "workspace_root": str(workspace_root),
        "manifest_path": str(manifest_path),
        "copied_files": len(copied_paths),
        "skipped_files": len(skipped_paths),
        "truncated": truncated,
    }


def _build_candidate_paths(
    *,
    source_path: Path,
    source_root: Path,
    target_type: str,
    findings: list[dict],
) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()

    if target_type == "file":
        rel = _safe_relative_path(source_path, source_root)
        if rel is not None:
            normalized = rel.as_posix()
            seen.add(normalized)
            candidates.append(rel)

    for item in findings:
        if not isinstance(item, dict):
            continue
        rel = _normalize_rel_path(str(item.get("file", "")))
        if rel is None:
            continue
        normalized = rel.as_posix()
        if normalized in seen:
            continue
        seen.add(normalized)
        candidates.append(rel)
    return candidates


def _seed_relative_files(source_root: Path, *, limit: int) -> list[Path]:
    seeded: list[Path] = []
    if limit <= 0:
        return seeded
    for path in source_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _CODE_SUFFIXES:
            continue
        rel = _safe_relative_path(path, source_root)
        if rel is None:
            continue
        seeded.append(rel)
        if len(seeded) >= limit:
            break
    return seeded


def _safe_relative_path(path: Path, root: Path) -> Path | None:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if not _is_within(resolved_path, resolved_root):
        return None
    try:
        return resolved_path.relative_to(resolved_root)
    except ValueError:
        return None


def _normalize_rel_path(value: str) -> Path | None:
    normalized = value.replace("\\", "/").strip().lstrip("/")
    if not normalized:
        return None
    rel_path = Path(normalized)
    if rel_path.is_absolute() or ".." in rel_path.parts:
        return None
    return rel_path


def _normalize_session_id(value: str) -> str:
    filtered = "".join(char for char in str(value) if char.isalnum() or char in {"-", "_"})
    return filtered or "scan"


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
