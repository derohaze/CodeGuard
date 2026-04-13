from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ParsedExternalPayload:
    items: list[dict[str, Any]]
    parser_name: str
    warnings: list[str] = field(default_factory=list)


def parse_external_payload_with_parser(
    payload_text: str,
    *,
    source_name: str | None = None,
) -> ParsedExternalPayload:
    parsed_json = _try_parse_json(payload_text)
    normalized_source = (source_name or "").strip().lower()
    parser = _resolve_parser(normalized_source)
    return parser(payload_text, parsed_json)


def parse_external_payload(payload_text: str, *, source_name: str | None = None) -> list[dict[str, Any]]:
    parsed = parse_external_payload_with_parser(payload_text, source_name=source_name)
    return parsed.items


def _resolve_parser(source_name: str):
    if source_name.startswith("cwe"):
        return _parse_cwe_payload
    if source_name.startswith("owasp"):
        return _parse_owasp_payload
    if source_name.startswith("semgrep"):
        return _parse_semgrep_payload
    if source_name.startswith("codeql"):
        return _parse_codeql_payload
    if source_name.startswith("juliet"):
        return _parse_juliet_payload
    return _parse_generic_payload


def _parse_cwe_payload(payload_text: str, parsed_json: Any) -> ParsedExternalPayload:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    if isinstance(parsed_json, dict):
        weaknesses = parsed_json.get("Weaknesses")
        if isinstance(weaknesses, dict):
            weaknesses = weaknesses.get("Weakness")
        if isinstance(weaknesses, list):
            for item in weaknesses:
                if not isinstance(item, dict):
                    continue
                weakness_id = _normalize_cwe_id(item.get("ID") or item.get("id") or item.get("weakness_id"))
                title = str(item.get("Name") or item.get("title") or "CWE entry").strip()
                summary = _coalesce_text(
                    item.get("Description"),
                    item.get("summary"),
                    item.get("Extended_Description"),
                )
                rows.append(
                    {
                        "item_type": "security_pattern",
                        "weakness_id": weakness_id,
                        "title": title,
                        "summary": summary,
                        "vulnerability_category": _to_category_slug(title),
                        "tags": _compact_tags(["cwe", item.get("Abstraction"), item.get("Structure")]),
                    }
                )

    if not rows:
        fallback = _parse_generic_payload(payload_text, parsed_json)
        warnings.append("cwe_specific_structure_not_found")
        return ParsedExternalPayload(items=fallback.items, parser_name="generic_parser", warnings=warnings)

    return ParsedExternalPayload(items=rows, parser_name="cwe_parser", warnings=warnings)


def _parse_owasp_payload(payload_text: str, parsed_json: Any) -> ParsedExternalPayload:
    rows: list[dict[str, Any]] = []
    if isinstance(parsed_json, dict):
        entries: list[tuple[str, Any]] = []
        if isinstance(parsed_json.get("items"), list):
            for index, item in enumerate(parsed_json["items"]):
                entries.append((f"item_{index}", item))
        else:
            entries.extend(parsed_json.items())
        for key, value in entries:
            if not isinstance(value, dict):
                continue
            title = str(value.get("title") or value.get("name") or key).strip()
            summary = _coalesce_text(value.get("summary"), value.get("description"))
            weakness = _normalize_cwe_id(value.get("weakness_id") or value.get("cwe"))
            rows.append(
                {
                    "item_type": "security_pattern",
                    "title": title,
                    "summary": summary,
                    "vulnerability_category": _to_category_slug(title),
                    "weakness_id": weakness,
                    "tags": _compact_tags(
                        ["owasp", value.get("category"), value.get("risk_level"), key]
                    ),
                    "remediation_notes": value.get("remediation_notes") or value.get("how_to_fix"),
                }
            )

    if not rows:
        fallback = _parse_generic_payload(payload_text, parsed_json)
        return ParsedExternalPayload(
            items=fallback.items,
            parser_name="generic_parser",
            warnings=["owasp_specific_structure_not_found"],
        )
    return ParsedExternalPayload(items=rows, parser_name="owasp_parser")


def _parse_semgrep_payload(payload_text: str, parsed_json: Any) -> ParsedExternalPayload:
    rows: list[dict[str, Any]] = []
    if isinstance(parsed_json, dict) and isinstance(parsed_json.get("rules"), list):
        for rule in parsed_json["rules"]:
            if not isinstance(rule, dict):
                continue
            metadata = rule.get("metadata") if isinstance(rule.get("metadata"), dict) else {}
            cwe_field = metadata.get("cwe") or metadata.get("cwe-id")
            if isinstance(cwe_field, list):
                cwe_field = cwe_field[0] if cwe_field else None
            language = None
            if isinstance(rule.get("languages"), list) and rule["languages"]:
                language = str(rule["languages"][0]).strip().lower()
            title = str(rule.get("message") or rule.get("id") or "Semgrep rule").strip()
            rows.append(
                {
                    "item_type": "framework_rule",
                    "rule_id": rule.get("id"),
                    "title": title,
                    "summary": _coalesce_text(metadata.get("shortDescription"), metadata.get("description")),
                    "language": language,
                    "framework": _first_string(metadata.get("technology")),
                    "vulnerability_category": _first_string(metadata.get("owasp")) or _to_category_slug(title),
                    "weakness_id": _normalize_cwe_id(cwe_field),
                    "unsafe_pattern": rule.get("pattern"),
                    "safe_pattern": rule.get("fix"),
                    "tags": _compact_tags(["semgrep", metadata.get("category"), metadata.get("confidence")]),
                }
            )

    if not rows:
        fallback = _parse_generic_payload(payload_text, parsed_json)
        return ParsedExternalPayload(
            items=fallback.items,
            parser_name="generic_parser",
            warnings=["semgrep_specific_structure_not_found"],
        )
    return ParsedExternalPayload(items=rows, parser_name="semgrep_parser")


def _parse_codeql_payload(payload_text: str, parsed_json: Any) -> ParsedExternalPayload:
    rows: list[dict[str, Any]] = []
    query_items: list[dict[str, Any]] = []
    if isinstance(parsed_json, dict) and isinstance(parsed_json.get("queries"), list):
        query_items = [item for item in parsed_json["queries"] if isinstance(item, dict)]
    elif isinstance(parsed_json, list):
        query_items = [item for item in parsed_json if isinstance(item, dict)]

    for query in query_items:
        tags = query.get("tags") if isinstance(query.get("tags"), list) else []
        weakness = None
        for tag in tags:
            if not isinstance(tag, str):
                continue
            maybe = _normalize_cwe_id(tag)
            if maybe:
                weakness = maybe
                break
        title = str(query.get("name") or query.get("title") or query.get("id") or "CodeQL query").strip()
        language = _first_string(query.get("language") or query.get("languages"))
        rows.append(
            {
                "item_type": "framework_rule",
                "rule_id": query.get("id"),
                "title": title,
                "summary": _coalesce_text(query.get("description"), query.get("help")),
                "language": language.lower() if isinstance(language, str) else None,
                "framework": _first_string(query.get("suite")),
                "vulnerability_category": _to_category_slug(title),
                "weakness_id": weakness,
                "tags": _compact_tags(["codeql", *tags]),
            }
        )

    if not rows:
        fallback = _parse_generic_payload(payload_text, parsed_json)
        return ParsedExternalPayload(
            items=fallback.items,
            parser_name="generic_parser",
            warnings=["codeql_specific_structure_not_found"],
        )
    return ParsedExternalPayload(items=rows, parser_name="codeql_parser")


def _parse_juliet_payload(payload_text: str, parsed_json: Any) -> ParsedExternalPayload:
    rows: list[dict[str, Any]] = []
    case_items: list[dict[str, Any]] = []
    if isinstance(parsed_json, dict) and isinstance(parsed_json.get("cases"), list):
        case_items = [item for item in parsed_json["cases"] if isinstance(item, dict)]
    elif isinstance(parsed_json, list):
        case_items = [item for item in parsed_json if isinstance(item, dict)]

    for case in case_items:
        cwe = _normalize_cwe_id(case.get("cwe") or case.get("cwe_id") or case.get("weakness_id"))
        title = str(case.get("title") or case.get("name") or cwe or "Juliet case").strip()
        vulnerability_category = _to_category_slug(case.get("category") or title)
        rows.append(
            {
                "item_type": "security_pattern",
                "title": title,
                "summary": _coalesce_text(case.get("summary"), case.get("description")),
                "language": _first_string(case.get("language")) or _first_string(case.get("languages")),
                "vulnerability_category": vulnerability_category,
                "weakness_id": cwe,
                "bad_example": case.get("bad_example") or case.get("bad"),
                "good_example": case.get("good_example") or case.get("good"),
                "tags": _compact_tags(["juliet", case.get("variant"), cwe]),
            }
        )

    if not rows:
        fallback = _parse_generic_payload(payload_text, parsed_json)
        return ParsedExternalPayload(
            items=fallback.items,
            parser_name="generic_parser",
            warnings=["juliet_specific_structure_not_found"],
        )
    return ParsedExternalPayload(items=rows, parser_name="juliet_parser")


def _parse_generic_payload(payload_text: str, parsed_json: Any) -> ParsedExternalPayload:
    if isinstance(parsed_json, list):
        return ParsedExternalPayload(
            items=[item for item in parsed_json if isinstance(item, dict)],
            parser_name="generic_parser",
        )
    if isinstance(parsed_json, dict):
        if isinstance(parsed_json.get("items"), list):
            return ParsedExternalPayload(
                items=[item for item in parsed_json["items"] if isinstance(item, dict)],
                parser_name="generic_parser",
            )
        return ParsedExternalPayload(items=[parsed_json], parser_name="generic_parser")

    lines = [line.strip() for line in payload_text.splitlines() if line.strip()]
    return ParsedExternalPayload(
        items=[{"title": line[:160], "summary": line[:1024]} for line in lines[:200]],
        parser_name="line_fallback_parser",
    )


def _try_parse_json(payload_text: str) -> Any:
    try:
        return json.loads(payload_text)
    except json.JSONDecodeError:
        return None


def _normalize_cwe_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    if text.startswith("CWE-"):
        return text
    match = re.search(r"CWE[-_: ]?(\d+)", text, re.IGNORECASE)
    if match:
        return f"CWE-{match.group(1)}"
    if text.isdigit():
        return f"CWE-{text}"
    return None


def _to_category_slug(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    sanitized = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return sanitized or None


def _coalesce_text(*parts: Any) -> str | None:
    for part in parts:
        if part is None:
            continue
        text = str(part).strip()
        if text:
            return text
    return None


def _first_string(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return None


def _compact_tags(values: list[Any]) -> list[str]:
    tags: set[str] = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, list):
            for item in value:
                if item is None:
                    continue
                normalized = str(item).strip().lower()
                if normalized:
                    tags.add(normalized)
            continue
        normalized = str(value).strip().lower()
        if normalized:
            tags.add(normalized)
    return sorted(tags)
