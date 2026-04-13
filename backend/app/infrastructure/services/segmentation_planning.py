from pathlib import Path

from app.infrastructure.services.scan_coverage import build_segment_work_items
from app.infrastructure.services.scan_modes import get_scan_mode_config


def build_scan_work_units(
    scan_mode: str,
    files: list[Path],
    source_root: Path,
    repository_artifacts: dict,
    repository_map: dict,
    file_segments: list[dict],
    target_type: str,
    traced_paths: dict,
) -> dict:
    config = get_scan_mode_config(scan_mode)
    base_items = build_segment_work_items(
        files=files,
        source_root=source_root,
        repository_artifacts=repository_artifacts,
        repository_map=repository_map,
        file_segments=file_segments,
        target_type=target_type,
        scan_mode=config.mode,
    )

    path_units = build_path_units(traced_paths, limit=config.max_path_units)
    if config.mode == "fast":
        ranked_items = sorted(
            base_items,
            key=lambda item: (
                -_review_item_priority(item),
                -int(item.get("signal_score", 0) or 0),
                str(item.get("file", "")),
                int(item.get("start_line", 0) or 0),
            ),
        )
        trimmed = []
        file_counts: dict[str, int] = {}
        for item in ranked_items:
            file_path = str(item.get("file", ""))
            next_count = file_counts.get(file_path, 0)
            per_file_limit = min(config.max_blocks_per_file, config.fast_per_file_limit)
            if next_count >= per_file_limit:
                continue
            file_counts[file_path] = next_count + 1
            trimmed.append(item)
            if len(trimmed) >= config.fast_risk_budget_items:
                break
            if len({entry["file"] for entry in trimmed}) >= config.max_hotspot_files and len(trimmed) >= config.max_hotspot_files * 2:
                break
        review_items = trimmed
    else:
        review_items = base_items

    return {
        "review_items": review_items,
        "path_units": path_units,
        "segmentation_summary": {
            "scan_mode": config.mode,
            "files_with_segments": len(file_segments),
            "block_units_total": sum(len(item.get("blocks", [])) for item in file_segments),
            "review_block_units": len(review_items),
            "path_units_total": len(path_units),
            "strategy": "full_repository_blocks" if config.mode == "deep" else "prioritized_hotspots",
        },
    }


def build_path_units(traced_paths: dict, limit: int) -> list[dict]:
    units: list[dict] = []
    for path in traced_paths.get("paths", [])[:limit]:
        units.append(
            {
                "path_id": _build_path_id(path),
                "source": path.get("source", {}),
                "sink": path.get("sink", {}),
                "nodes": path.get("nodes", []),
                "path_hint": path.get("path_hint", ""),
                "path_type": path.get("path_type", "intra_file"),
                "has_sanitizer": bool(path.get("has_sanitizer")),
                "confidence": int(path.get("confidence", 0)),
                "line_sequence": path.get("line_sequence", []),
            }
        )
    return units


def _build_path_id(path: dict) -> str:
    sink = path.get("sink", {})
    source = path.get("source", {})
    return f"{source.get('file', 'unknown')}:{source.get('line', 0)}->{sink.get('file', 'unknown')}:{sink.get('line', 0)}"


def _review_item_priority(item: dict) -> int:
    score = int(item.get("signal_score", 0) or 0) * 3
    review_focus = str(item.get("review_focus", "")).lower()
    block_kind = str(item.get("block_kind", "")).lower()
    rationale = str(item.get("rationale", "")).lower()
    attack_surface = str(item.get("related_attack_surface", "")).lower()
    path_type = str(item.get("path_type", "")).lower()

    if path_type == "cross_file":
        score += 18
    elif path_type == "intra_file":
        score += 9

    if any(token in review_focus for token in ("command", "deserial", "query", "sql", "token", "auth")):
        score += 12
    if any(token in rationale for token in ("request entrypoint", "auth boundary", "subprocess", "query", "network")):
        score += 8
    if any(token in attack_surface for token in ("public", "api", "graphql", "auth", "admin")):
        score += 6
    if block_kind in {"function", "route", "handler"}:
        score += 6

    return score
