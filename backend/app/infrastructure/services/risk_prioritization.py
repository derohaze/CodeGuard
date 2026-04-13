def prioritize_review_queue(work_items: list[dict], path_units: list[dict], scan_mode: str) -> dict:
    ranked_paths = sorted(
        path_units,
        key=lambda item: (
            -_path_priority_score(item),
            str(item.get("sink", {}).get("file", "")),
            int(item.get("sink", {}).get("line", 0)),
        ),
    )

    path_rank_lookup = {str(item.get("sink", {}).get("file", "")): index for index, item in enumerate(ranked_paths)}
    path_score_lookup = {
        str(item.get("sink", {}).get("file", "")): _path_priority_score(item)
        for item in ranked_paths
    }
    ranked_work_items = sorted(
        work_items,
        key=lambda item: (
            path_rank_lookup.get(str(item.get("file", "")), 999999),
            -_review_item_priority_score(item, path_score_lookup.get(str(item.get("file", "")), 0)),
            str(item.get("file", "")),
            _safe_int(item.get("start_line", 1)),
        ),
    )

    return {
        "review_items": ranked_work_items,
        "path_units": ranked_paths,
        "review_queue_summary": {
            "scan_mode": scan_mode,
            "ranked_review_items": len(ranked_work_items),
            "ranked_path_units": len(ranked_paths),
            "cross_file_paths": sum(1 for item in ranked_paths if item.get("path_type") == "cross_file"),
            "sanitized_paths": sum(1 for item in ranked_paths if item.get("has_sanitizer")),
            "high_risk_path_units": sum(1 for item in ranked_paths if _path_priority_score(item) >= 90),
        },
    }


def _path_priority_score(item: dict) -> int:
    score = _safe_int(item.get("confidence", 0))
    sink_kind = str(item.get("sink", {}).get("kind", ""))
    if sink_kind in {"command_execution", "unsafe_deserialization"}:
        score += 24
    elif sink_kind in {"query_execution"}:
        score += 16
    elif sink_kind in {"outbound_request", "filesystem_access"}:
        score += 10
    if item.get("path_type") == "cross_file":
        score += 12
    if item.get("has_sanitizer"):
        score -= 28
    line_span = _path_line_span(item)
    if line_span >= 4:
        score += min(8, line_span)
    return score


def _review_item_priority_score(item: dict, path_score: int) -> int:
    score = _safe_int(item.get("signal_score", 0)) * 3 + path_score
    review_focus = str(item.get("review_focus", "")).lower()
    rationale = str(item.get("rationale", "")).lower()
    path_type = str(item.get("path_type", "")).lower()

    if path_type == "cross_file":
        score += 10
    if any(token in review_focus for token in ("command", "deserial", "query", "sql", "auth", "token")):
        score += 8
    if any(token in rationale for token in ("request entrypoint", "auth boundary", "subprocess", "query", "network")):
        score += 6
    return score


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _path_line_span(item: dict) -> int:
    lines = item.get("line_sequence", [])
    if not isinstance(lines, list) or not lines:
        return 0
    numeric_lines = [_safe_int(line, 0) for line in lines if _safe_int(line, 0) > 0]
    if not numeric_lines:
        return 0
    return max(numeric_lines) - min(numeric_lines)
