from pathlib import Path

from app.infrastructure.services.scan_modes import get_scan_mode_config


def build_scan_plan(
    source_path: Path,
    target_type: str,
    preset: str,
    scan_mode: str,
    repository_profile: dict | None = None,
) -> dict:
    config = get_scan_mode_config(scan_mode)
    file_count = int((repository_profile or {}).get("file_count", 0))
    languages = [str(item) for item in (repository_profile or {}).get("languages", [])[:4]]

    return {
        "scan_mode": config.mode,
        "mode_label": config.label,
        "target_type": target_type,
        "preset": preset,
        "source_name": source_path.name,
        "source_path": str(source_path),
        "multi_pass": config.multi_pass,
        "validation_passes": config.validation_passes,
        "coverage_target_percent": config.target_coverage,
        "work_unit_strategy": {
            "files": "full_traversal" if config.mode == "deep" else "prioritized_subset",
            "blocks": "all_blocks" if config.mode == "deep" else "hot_blocks",
            "paths": "all_candidate_paths" if config.mode == "deep" else "high_risk_paths",
            "fast_risk_budget_items": config.fast_risk_budget_items,
            "fast_per_file_limit": config.fast_per_file_limit,
        },
        "time_budget": {
            "effort": "high" if config.mode == "deep" else "medium",
            "batch_style": "multi_pass" if config.multi_pass else "single_pass",
        },
        "repository_hint": {
            "supported_files": file_count,
            "languages": languages,
        },
    }

