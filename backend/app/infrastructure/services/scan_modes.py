from dataclasses import dataclass
from typing import Literal


ScanMode = Literal["fast", "deep"]


@dataclass(frozen=True, slots=True)
class ScanModeConfig:
    mode: ScanMode
    label: str
    target_coverage: int
    max_hotspot_files: int
    max_blocks_per_file: int
    max_path_units: int
    multi_pass: bool
    validation_passes: int
    validation_candidates_per_pass: int
    fast_risk_budget_items: int
    fast_per_file_limit: int


SCAN_MODE_CONFIGS: dict[ScanMode, ScanModeConfig] = {
    "fast": ScanModeConfig(
        mode="fast",
        label="Fast Scan",
        target_coverage=45,
        max_hotspot_files=18,
        max_blocks_per_file=4,
        max_path_units=24,
        multi_pass=False,
        validation_passes=1,
        validation_candidates_per_pass=24,
        fast_risk_budget_items=32,
        fast_per_file_limit=3,
    ),
    "deep": ScanModeConfig(
        mode="deep",
        label="Deep Scan",
        target_coverage=95,
        max_hotspot_files=9999,
        max_blocks_per_file=9999,
        max_path_units=9999,
        multi_pass=True,
        validation_passes=2,
        validation_candidates_per_pass=48,
        fast_risk_budget_items=9999,
        fast_per_file_limit=9999,
    ),
}


def get_scan_mode_config(mode: str | None) -> ScanModeConfig:
    normalized = (mode or "deep").strip().lower()
    if normalized == "fast":
        return SCAN_MODE_CONFIGS["fast"]
    return SCAN_MODE_CONFIGS["deep"]
