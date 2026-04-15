from __future__ import annotations

import json
import re
from textwrap import shorten


TASK_PROMPT_LIMITS = {
    ("repository_map", "repository_profile"): {"list_limit": 10, "string_limit": 220},
    ("repository_map", "repository_artifacts"): {"list_limit": 10, "string_limit": 220},
    ("path_review", "repository_profile"): {"list_limit": 8, "string_limit": 180},
    ("path_review", "repository_map"): {"list_limit": 8, "string_limit": 180},
    ("path_review", "work_items"): {"list_limit": 10, "string_limit": 180},
    ("finding_validate", "repository_profile"): {"list_limit": 8, "string_limit": 180},
    ("finding_validate", "repository_map"): {"list_limit": 8, "string_limit": 180},
    ("finding_validate", "findings"): {"list_limit": 12, "string_limit": 180},
    ("verdict", "repository_profile"): {"list_limit": 7, "string_limit": 160},
    ("verdict", "repository_map"): {"list_limit": 8, "string_limit": 180},
    ("verdict", "findings"): {"list_limit": 10, "string_limit": 160},
    ("explain", "remediation_context"): {"list_limit": 7, "string_limit": 220},
    ("fix_draft", "remediation_context"): {"list_limit": 9, "string_limit": 320},
    ("fix_validate", "remediation_context"): {"list_limit": 8, "string_limit": 300},
    ("fix_validate", "remediation_draft"): {"list_limit": 10, "string_limit": 420},
}

ALLOWED_FIX_TYPES = {"full_fix", "partial_mitigation", "temporary_guard", "risky_workaround"}
ALLOWED_SECURITY_STRENGTH = {"high", "medium", "low"}
ALLOWED_REGRESSION_RISK = {"low", "medium", "high"}


def json_for_prompt(value, *, max_chars: int) -> str:
    compact = value
    for limits in (
        {"list_limit": 12, "string_limit": 400},
        {"list_limit": 8, "string_limit": 240},
        {"list_limit": 5, "string_limit": 160},
        {"list_limit": 3, "string_limit": 120},
        {"list_limit": 2, "string_limit": 80},
    ):
        compact = compact_for_prompt(value, **limits)
        dumped = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        if len(dumped) <= max_chars:
            return dumped
    dumped = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(
        {
            "truncated": True,
            "preview": dumped[: max(0, max_chars - 80)],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def json_for_task_prompt(task_name: str, section: str, value, *, max_chars: int) -> str:
    defaults = TASK_PROMPT_LIMITS.get((task_name, section)) or TASK_PROMPT_LIMITS.get((task_name, "*"))
    if not defaults:
        return json_for_prompt(value, max_chars=max_chars)

    list_limit = int(defaults["list_limit"])
    string_limit = int(defaults["string_limit"])
    compact = value
    for shrink in (1.0, 0.85, 0.7, 0.55, 0.4):
        compact = compact_for_prompt(
            value,
            list_limit=max(2, round(list_limit * shrink)),
            string_limit=max(80, round(string_limit * shrink)),
        )
        dumped = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        if len(dumped) <= max_chars:
            return dumped
    return json_for_prompt(compact, max_chars=max_chars)


def compact_for_prompt(value, *, list_limit: int, string_limit: int):
    if isinstance(value, dict):
        items = list(value.items())
        compact: dict = {}
        for index, (key, item) in enumerate(items):
            if index >= list_limit:
                compact["_truncated_keys"] = len(items) - list_limit
                break
            compact[str(key)] = compact_for_prompt(item, list_limit=list_limit, string_limit=string_limit)
        return compact
    if isinstance(value, list):
        compact_items = [
            compact_for_prompt(item, list_limit=list_limit, string_limit=string_limit)
            for item in value[:list_limit]
        ]
        if len(value) > list_limit:
            compact_items.append({"_truncated_items": len(value) - list_limit})
        return compact_items
    if isinstance(value, str):
        if len(value) <= string_limit:
            return value
        return f"{value[:string_limit]}...<truncated>"
    return value


def extract_json(content: str) -> dict:
    if not isinstance(content, str) or not content.strip():
        return {}

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, flags=re.DOTALL | re.IGNORECASE)
    candidates: list[str] = []
    if fenced_match:
        candidates.append(fenced_match.group(1))

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(content[start : end + 1])

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    for index, char in enumerate(content):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(content[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def normalize_priority_path(item: dict) -> dict:
    priority = str(item.get("priority", "high")).lower()
    if priority not in {"critical", "high", "medium"}:
        priority = "high"
    return {
        "file": str(item.get("file", "")),
        "reason": shorten(str(item.get("reason", "")), width=160, placeholder="..."),
        "priority": priority,
        "attack_surface": shorten(str(item.get("attack_surface", "")), width=120, placeholder="..."),
        "review_focus": shorten(str(item.get("review_focus", "")), width=160, placeholder="..."),
    }


def normalize_finding(item: dict) -> dict:
    return {
        "severity": str(item.get("severity", "medium")).lower(),
        "title": str(item.get("title", "AI-confirmed security risk")),
        "file": str(item.get("file", "")),
        "line": int(item.get("line", 1)),
        "line_end": int(item.get("line_end", item.get("line", 1))),
        "category": str(item.get("category", "Security review")),
        "confidence": int(item.get("confidence", 70)),
        "summary": shorten(str(item.get("summary", "")), width=240, placeholder="..."),
        "impact": shorten(str(item.get("impact", "")), width=180, placeholder="..."),
        "explanation": shorten(str(item.get("explanation", "")), width=360, placeholder="..."),
        "source_hint": shorten(str(item.get("source_hint", "")), width=120, placeholder="..."),
        "sink_hint": shorten(str(item.get("sink_hint", "")), width=120, placeholder="..."),
        "path_hint": shorten(str(item.get("path_hint", "")), width=220, placeholder="..."),
        "attack_input": shorten(str(item.get("attack_input", "")), width=180, placeholder="..."),
        "attack_execution": shorten(str(item.get("attack_execution", "")), width=180, placeholder="..."),
        "attack_result": shorten(str(item.get("attack_result", "")), width=180, placeholder="..."),
        "evidence": shorten(str(item.get("evidence", "")), width=300, placeholder="..."),
        "audit_log": [str(entry) for entry in item.get("audit_log", [])][:5],
        "fix_suggestions": [
            {
                "id": str(suggestion.get("id", "recommended")),
                "label": str(suggestion.get("label", "Fix")),
                "profile": str(suggestion.get("profile", "recommended")),
                "description": str(suggestion.get("description", "Reduce exposure at the trust boundary and harden the sink.")),
            }
            for suggestion in item.get("fix_suggestions", [])
            if isinstance(suggestion, dict)
        ],
    }


def compact_findings(findings: list[dict], limit: int) -> list[dict]:
    compact: list[dict] = []
    for item in findings[:limit]:
        compact.append(
            {
                "severity": str(item.get("severity", "medium")).lower(),
                "title": str(item.get("title", "Security finding")),
                "file": str(item.get("file", "")),
                "line": int(item.get("line", 1)),
                "line_end": int(item.get("line_end", item.get("line", 1))),
                "category": str(item.get("category", "Security review")),
                "confidence": int(item.get("confidence", 70)),
                "summary": shorten(str(item.get("summary", "")), width=180, placeholder="..."),
                "source_hint": shorten(str(item.get("source_hint", "")), width=100, placeholder="..."),
                "sink_hint": shorten(str(item.get("sink_hint", "")), width=100, placeholder="..."),
                "path_hint": shorten(str(item.get("path_hint", "")), width=180, placeholder="..."),
                "evidence": shorten(str(item.get("evidence", "")), width=220, placeholder="..."),
            }
        )
    return compact


def normalize_analysis_brief(parsed: dict) -> dict | None:
    if not isinstance(parsed, dict):
        return None

    def normalize_items(key: str, *, limit: int, width: int) -> list[str]:
        items = parsed.get(key, [])
        if not isinstance(items, list):
            return []
        normalized: list[str] = []
        for item in items:
            text = shorten(str(item).strip(), width=width, placeholder="...")
            if text and text not in normalized:
                normalized.append(text)
            if len(normalized) >= limit:
                break
        return normalized

    score_explanation = shorten(str(parsed.get("score_explanation", "")).strip(), width=280, placeholder="...")
    brief = {
        "score_explanation": score_explanation,
        "potential_risks": normalize_items("potential_risks", limit=4, width=220),
        "security_observations": normalize_items("security_observations", limit=4, width=220),
        "analysis_limitations": normalize_items("analysis_limitations", limit=4, width=220),
        "attack_thinking": normalize_items("attack_thinking", limit=4, width=220),
        "next_steps": normalize_items("next_steps", limit=5, width=220),
    }
    if score_explanation or any(brief[key] for key in brief if key != "score_explanation"):
        return brief
    return None


def normalize_fix_strategy(item: dict) -> dict:
    if not isinstance(item, dict):
        item = {}
    kind = str(item.get("kind", "guard")).strip().lower()
    if kind not in {"refactor", "guard", "sanitization"}:
        kind = "guard"
    fix_type = str(item.get("fix_type", "partial_mitigation")).strip().lower()
    if fix_type not in ALLOWED_FIX_TYPES:
        fix_type = "partial_mitigation"
    security_strength = str(item.get("security_strength", "medium")).strip().lower()
    if security_strength not in ALLOWED_SECURITY_STRENGTH:
        security_strength = "medium"
    regression_risk = str(item.get("regression_risk", "medium")).strip().lower()
    if regression_risk not in ALLOWED_REGRESSION_RISK:
        regression_risk = "medium"
    return {
        "id": str(item.get("id", kind)),
        "label": str(item.get("label", "Fix strategy")),
        "kind": kind,
        "confidence": max(0, min(100, int(item.get("confidence", 70) or 70))),
        "impact": str(item.get("impact", "medium")),
        "effort": str(item.get("effort", "medium")),
        "summary": shorten(str(item.get("summary", "")), width=220, placeholder="..."),
        "rationale": shorten(str(item.get("rationale", "")), width=320, placeholder="..."),
        "diff": str(item.get("diff", "")),
        "recommended": bool(item.get("recommended", False)),
        "fix_type": fix_type,
        "security_strength": security_strength,
        "regression_risk": regression_risk,
        "selection_reason": shorten(str(item.get("selection_reason", "")), width=240, placeholder="..."),
        "non_selection_reason": shorten(str(item.get("non_selection_reason", "")), width=220, placeholder="..."),
        "residual_risks": [shorten(str(note), width=160, placeholder="...") for note in item.get("residual_risks", []) if str(note).strip()][:4],
        "policy_compliant": bool(item.get("policy_compliant", True)),
        "policy_violations": [shorten(str(note), width=180, placeholder="...") for note in item.get("policy_violations", []) if str(note).strip()][:4],
    }


def normalize_patch_candidate(item: dict) -> dict:
    if not isinstance(item, dict):
        return {
            "file": "",
            "language": "",
            "summary": "",
            "diff": "",
            "validation_notes": [],
            "before_snippet": "",
            "after_snippet": "",
        }
    fix_type = str(item.get("fix_type", "partial_mitigation")).strip().lower()
    if fix_type not in ALLOWED_FIX_TYPES:
        fix_type = "partial_mitigation"
    return {
        "file": str(item.get("file", "")),
        "language": str(item.get("language", "")),
        "summary": shorten(str(item.get("summary", "")), width=220, placeholder="..."),
        "diff": str(item.get("diff", "")),
        "validation_notes": [str(note) for note in item.get("validation_notes", []) if str(note).strip()][:6],
        "before_snippet": str(item.get("before_snippet", "")),
        "after_snippet": str(item.get("after_snippet", "")),
        "fix_type": fix_type,
        "rationale": shorten(str(item.get("rationale", "")), width=240, placeholder="..."),
        "residual_risks": [shorten(str(note), width=160, placeholder="...") for note in item.get("residual_risks", []) if str(note).strip()][:4],
        "manual_review_required": bool(item.get("manual_review_required", False)),
    }


def normalize_remediation_payload(
    parsed: dict,
    *,
    fallback_review_summary: str = "",
    fallback_recommended_strategy_id: str | None = None,
    fallback_strategies: list[dict] | None = None,
    fallback_patch: dict | None = None,
) -> dict:
    parsed = parsed if isinstance(parsed, dict) else {}
    fallback_strategies = fallback_strategies or []
    fallback_patch = fallback_patch or {}

    strategies = [
        normalize_fix_strategy(item)
        for item in parsed.get("strategies", fallback_strategies)
        if isinstance(item, dict)
    ]
    recommended_strategy_id = str(
        parsed.get("recommended_strategy_id", fallback_recommended_strategy_id or "")
    ).strip() or None
    strategies, recommended_strategy = _normalize_recommended_strategy(strategies, recommended_strategy_id)

    patch_source = parsed.get("patch", fallback_patch)
    patch = normalize_patch_candidate(patch_source)
    top_level_validation_notes = [
        str(item).strip()
        for item in parsed.get("validation_notes", [])
        if str(item).strip()
    ][:6]
    patch["validation_notes"] = _merge_unique_notes(
        patch.get("validation_notes", []),
        top_level_validation_notes,
    )[:6]
    if recommended_strategy is not None:
        patch = _enrich_patch_from_strategy(patch, recommended_strategy)

    return {
        "review_summary": shorten(
            str(parsed.get("review_summary", fallback_review_summary)),
            width=280,
            placeholder="...",
        ),
        "recommended_strategy_id": recommended_strategy["id"] if recommended_strategy is not None else None,
        "strategies": strategies,
        "patch": patch,
    }


def _normalize_recommended_strategy(
    strategies: list[dict],
    recommended_strategy_id: str | None,
) -> tuple[list[dict], dict | None]:
    if not strategies:
        return [], None

    selected_id = recommended_strategy_id
    if selected_id is None:
        selected = next((item for item in strategies if item.get("recommended")), None)
        if selected is None:
            selected = max(
                strategies,
                key=lambda item: (
                    1 if item.get("policy_compliant") else 0,
                    1 if item.get("fix_type") == "full_fix" else 0,
                    1 if item.get("security_strength") == "high" else 0,
                    int(item.get("confidence", 0)),
                ),
            )
        selected_id = str(selected.get("id", "")).strip() or None

    normalized: list[dict] = []
    selected_strategy: dict | None = None
    for item in strategies:
        current = dict(item)
        is_selected = selected_id is not None and str(current.get("id", "")).strip() == selected_id
        current["recommended"] = is_selected
        if is_selected:
            selected_strategy = current
        normalized.append(current)

    if selected_strategy is None:
        normalized[0]["recommended"] = True
        selected_strategy = normalized[0]

    return normalized, selected_strategy


def _enrich_patch_from_strategy(patch: dict, strategy: dict) -> dict:
    enriched = dict(patch)
    if not str(enriched.get("fix_type", "")).strip() or enriched.get("fix_type") == "partial_mitigation":
        enriched["fix_type"] = strategy.get("fix_type", "partial_mitigation")
    if not str(enriched.get("rationale", "")).strip():
        enriched["rationale"] = strategy.get("selection_reason") or strategy.get("rationale", "")
    if not enriched.get("residual_risks"):
        enriched["residual_risks"] = list(strategy.get("residual_risks", []))[:4]
    if not enriched.get("manual_review_required"):
        enriched["manual_review_required"] = (
            strategy.get("fix_type") != "full_fix"
            or strategy.get("regression_risk") == "high"
            or not strategy.get("policy_compliant", True)
        )
    if strategy.get("policy_violations"):
        enriched["validation_notes"] = _merge_unique_notes(
            enriched.get("validation_notes", []),
            strategy.get("policy_violations", []),
        )[:6]
    return enriched


def _merge_unique_notes(base: list[str], extra: list[str]) -> list[str]:
    merged: list[str] = []
    for item in [*base, *extra]:
        note = str(item).strip()
        if note and note not in merged:
            merged.append(note)
    return merged


def extract_review_payload(content: str) -> dict:
    parsed = extract_json(content)
    findings = parsed.get("findings", [])
    normalized_findings = []
    if isinstance(findings, list):
        for item in findings:
            if not isinstance(item, dict):
                continue
            normalized_findings.append(normalize_finding(item))

    return {
        "review_note": shorten(str(parsed.get("review_note", "")), width=180, placeholder="..."),
        "repository_summary": shorten(str(parsed.get("repository_summary", parsed.get("safe_summary", ""))), width=260, placeholder="..."),
        "safe_summary": shorten(str(parsed.get("safe_summary", "")), width=260, placeholder="..."),
        "findings": normalized_findings,
    }
