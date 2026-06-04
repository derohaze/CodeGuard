from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from hashlib import sha256
from typing import Optional

from app.infrastructure.intelligence.continuous.models import IntelligenceScenario, SearchResult
from app.infrastructure.redact import redact_text


BUILTIN_SCENARIOS: list[IntelligenceScenario] = [
    IntelligenceScenario(
        id="builtin-node-pm2-source-exposure",
        title="Node source exposure should check PM2 deployment files",
        category="recon-gap",
        triggers=["server.js", "package.json", "node", "express", "source leak", "deployment", "nginx"],
        technologies=["Node.js", "Express", "PM2"],
        lesson="When Node source files or package metadata appear during recon, include PM2 and process-manager deployment files in the next enumeration pass.",
        recommended_checks=["ecosystem.config.js", "ecosystem.config.cjs", "ecosystem.config.mjs", "pm2.json", "process.json", "app.js", "index.js"],
        avoid_missing=["ecosystem.config.js", "PM2 deployment files"],
        source="builtin seed",
        created_at="2026-06-03T00:00:00.000Z",
        confidence=0.95,
        scope="builtin",
    ),
]


class IntelligenceStore:
    def __init__(self, project_dir: str | None = None, home_dir: str | None = None):
        cwd = project_dir or os.getcwd()
        home = home_dir or os.path.expanduser("~")
        self._project_path = os.path.join(cwd, ".aegix", "intelligence", "scenarios.jsonl")
        self._personal_path = os.path.join(home, ".aegix", "intelligence", "scenarios.jsonl")

    def list(self) -> list[IntelligenceScenario]:
        scenarios: list[IntelligenceScenario] = []
        scenarios.extend(self._read_jsonl(self._project_path, "project"))
        scenarios.extend(self._read_jsonl(self._personal_path, "personal"))
        scenarios.extend(BUILTIN_SCENARIOS)
        return self._dedupe(scenarios)

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        tokens = self._tokenize(query)
        if not tokens:
            return []
        results: list[SearchResult] = []
        for scenario in self.list():
            score, matched = self._score(scenario, tokens)
            if score <= 0:
                continue
            results.append(SearchResult(scenario=scenario, score=score, matched=matched))
        results.sort(key=lambda r: (-r.score, -r.scenario.confidence))
        return results[:max(1, limit)]

    async def append(self, scenario_data: dict) -> Optional[IntelligenceScenario]:
        scope = scenario_data.get("scope", "project")
        scenario = IntelligenceScenario(
            id=scenario_data.get("id") or self._new_id(),
            title=str(scenario_data.get("title", "")),
            category=str(scenario_data.get("category", "")),
            triggers=scenario_data.get("triggers", []),
            technologies=scenario_data.get("technologies", []),
            lesson=str(scenario_data.get("lesson", "")),
            recommended_checks=scenario_data.get("recommended_checks", []),
            avoid_missing=scenario_data.get("avoid_missing", []),
            source=str(scenario_data.get("source", "")),
            source_session_id=scenario_data.get("source_session_id"),
            created_at=scenario_data.get("created_at") or datetime.now(timezone.utc).isoformat(),
            updated_at=scenario_data.get("updated_at"),
            confidence=float(scenario_data.get("confidence", 0.7)),
            scope=scope if scope in ("personal", "project") else "project",
        )
        if self._has_duplicate(scenario):
            return None
        path = self._personal_path if scope == "personal" else self._project_path
        directory = os.path.dirname(path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(scenario.model_dump()) + "\n")
        return scenario

    async def learn_from_text(self, text: str, source_session_id: str | None = None) -> list[IntelligenceScenario]:
        cleaned = redact_text(text)
        learned: list[IntelligenceScenario] = []
        for candidate in self._extract_scenarios(cleaned, source_session_id):
            project_saved = await self.append({**candidate, "scope": "project"})
            if project_saved:
                learned.append(project_saved)
        return learned

    def _has_duplicate(self, scenario: IntelligenceScenario) -> bool:
        wanted_title = self._normalize_key(scenario.title)
        wanted_category = self._normalize_key(scenario.category)
        path = self._personal_path if scenario.scope == "personal" else self._project_path
        for existing in self._read_jsonl(path, scenario.scope):
            if existing.id == scenario.id:
                return True
            if (self._normalize_key(existing.title) == wanted_title
                    and self._normalize_key(existing.category) == wanted_category):
                return True
        return False

    def _read_jsonl(self, path: str, fallback_scope: str) -> list[IntelligenceScenario]:
        if not os.path.isfile(path):
            return []
        scenarios: list[IntelligenceScenario] = []
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        data.setdefault("scope", fallback_scope)
                        scenarios.append(IntelligenceScenario(**data))
                    except (json.JSONDecodeError, Exception):
                        pass
        except OSError:
            pass
        return scenarios

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for raw in re.findall(r"[a-z0-9_.-]{2,}", text.lower()):
            token = raw.strip("-_.")
            if len(token) >= 2 and token not in seen:
                seen.add(token)
                out.append(token)
        return out[:300]

    @staticmethod
    def _score(scenario: IntelligenceScenario, query_tokens: list[str]):
        fields: list[tuple[str, int, str]] = [
            (scenario.title, 7, "title"),
            (scenario.category, 5, "category"),
            (" ".join(scenario.triggers), 8, "triggers"),
            (" ".join(scenario.technologies), 6, "technology"),
            (" ".join(scenario.recommended_checks), 5, "recommended_checks"),
            (" ".join(scenario.avoid_missing), 4, "avoid_missing"),
            (scenario.lesson, 2, "lesson"),
        ]
        score = 0.0
        matched: list[str] = []
        for token in query_tokens:
            for text, weight, label in fields:
                lower = text.lower()
                if token in lower or (token.replace(".", " ") in lower if "." in token else False):
                    score += weight
                    matched.append(f"{label}:{token}")
        if score > 0:
            score += scenario.confidence
        return score, matched

    @staticmethod
    def _normalize_key(s: str) -> str:
        s = s.lower().replace("**", "").replace("`", "")
        s = re.sub(r"^\d+\.\s*", "", s)
        return re.sub(r"\s+", " ", s).strip()

    @staticmethod
    def _dedupe(scenarios: list[IntelligenceScenario]) -> list[IntelligenceScenario]:
        seen: set[str] = set()
        out: list[IntelligenceScenario] = []
        for s in scenarios:
            key = f"{IntelligenceStore._normalize_key(s.category)}\n{IntelligenceStore._normalize_key(s.title)}"
            if s.id in seen or key in seen:
                continue
            seen.add(s.id)
            seen.add(key)
            out.append(s)
        return out

    @staticmethod
    def _new_id() -> str:
        return f"scn_{sha256(str(time.time_ns()).encode()).hexdigest()[:16]}"

    @staticmethod
    def _extract_scenarios(text: str, source_session_id: str | None = None) -> list[dict]:
        out: list[dict] = []
        lower = text.lower()

        if ("server.js" in lower or "package.json" in lower) and \
           any(x in lower for x in ["node", "express", "source"]):
            out.append({
                "title": "Node source exposure should check PM2 deployment files",
                "category": "recon-gap",
                "triggers": ["server.js", "package.json", "node", "express", "source leak", "deployment"],
                "technologies": ["Node.js", "Express", "PM2"],
                "lesson": "When Node source files or package metadata appear during recon, include PM2 and process-manager deployment files.",
                "recommended_checks": ["ecosystem.config.js", "ecosystem.config.cjs", "pm2.json", "process.json"],
                "avoid_missing": ["ecosystem.config.js", "PM2 deployment files"],
                "source": "automatic learning",
                "source_session_id": source_session_id,
                "confidence": 0.9,
            })

        sections = _split_markdown_sections(text)
        preference_items = _section_items(sections, ["user preferences and working style", "user preferences", "working style"])
        for item in preference_items[:12]:
            title = _clean_text(item)[:90]
            out.append({
                "title": f"User preference: {title}",
                "category": "user-preference",
                "triggers": [item[:100]],
                "technologies": [],
                "lesson": f"Adapt future responses to this user preference: {_clean_text(item)[:500]}",
                "recommended_checks": ["apply this preference when relevant"],
                "avoid_missing": [_clean_text(item)[:160]],
                "source": "continuous learning",
                "source_session_id": source_session_id,
                "confidence": 0.82,
            })

        decision_items = _section_items(sections, ["decisions and assumptions", "important decisions"])
        for item in decision_items[:10]:
            title = _clean_text(item)[:90]
            out.append({
                "title": f"Decision memory: {title}",
                "category": "decision",
                "triggers": [item[:100]],
                "technologies": [],
                "lesson": f"Carry forward this decision: {_clean_text(item)[:500]}",
                "recommended_checks": ["reuse this decision unless new evidence invalidates it"],
                "avoid_missing": [_clean_text(item)[:160]],
                "source": "continuous learning",
                "source_session_id": source_session_id,
                "confidence": 0.74,
            })

        proven_items = _section_items(sections, ["what worked well", "proven workflows", "successful solutions"])
        for item in proven_items[:10]:
            if not _is_workflow_like(item):
                continue
            title = _clean_text(item)[:90]
            out.append({
                "title": f"Proven workflow: {title}",
                "category": "proven-workflow",
                "triggers": [item[:100]],
                "technologies": [],
                "lesson": f"This approach worked before: {_clean_text(item)[:500]}",
                "recommended_checks": _extract_checks(item),
                "avoid_missing": ["reuse proven workflow when context matches"],
                "source": "continuous learning",
                "source_session_id": source_session_id,
                "confidence": 0.76,
            })

        failure_items = _section_items(sections, ["what failed and why", "past mistakes", "lessons learned"])
        for item in failure_items[:12]:
            if not _is_failure_like(item):
                continue
            title = _clean_text(item)[:90]
            out.append({
                "title": f"Lesson learned: {title}",
                "category": "lesson-learned",
                "triggers": [item[:100]],
                "technologies": [],
                "lesson": f"Avoid repeating: {_clean_text(item)[:500]}",
                "recommended_checks": ["choose a better strategy before repeating this action"],
                "avoid_missing": [_clean_text(item)[:160]],
                "source": "continuous learning",
                "source_session_id": source_session_id,
                "confidence": 0.8,
            })

        return _dedupe_inputs(out)[:25]


def _split_markdown_sections(text: str):
    sections: dict[str, list[str]] = {}
    current = "summary"
    sections[current] = []
    for line in text.split("\n"):
        m = re.match(r"^#{1,3}\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).lower().replace("*", "").replace("`", "").strip()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _section_items(sections: dict[str, list[str]], names: list[str]):
    out: list[str] = []
    for name in names:
        key = name.lower().replace("*", "").replace("`", "").strip()
        for line in sections.get(key, []):
            trimmed = line.strip()
            if not trimmed:
                continue
            bullet = re.sub(r"^[-*]\s+", "", trimmed)
            bullet = re.sub(r"^\d+\.\s+", "", bullet)
            bullet = re.sub(r"^\[[ xX]\]\s+", "", bullet).strip()
            if bullet and len(bullet) >= 12:
                out.append(bullet)
    return out[:40]


def _clean_text(text: str, max_len: int = 0) -> str:
    result = text.replace("**", "").replace("`", "").replace("\n", " ").strip()
    result = re.sub(r"\s+", " ", result)
    if max_len and len(result) > max_len:
        result = result[:max_len - 1] + "…"
    return result


def _is_workflow_like(item: str) -> bool:
    return bool(re.search(r"\b(?:worked|successful|proven|use|run|command|workflow|approach|fixed|verified|passed)\b", item, re.I))


def _is_failure_like(item: str) -> bool:
    return bool(re.search(r"\b(?:failed|failure|mistake|wrong|avoid|blocked|error|regression|missed)\b", item, re.I))


def _extract_checks(item: str) -> list[str]:
    checks = re.findall(r"[a-z0-9_.-]+\.(?:js|json|py|ts|go|rb|php|env)", item.lower())
    return checks[:8] or [_clean_text(item)[:160]]


def _dedupe_inputs(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in items:
        key = f"{_normalize_key_str(item.get('category', ''))}\n{_normalize_key_str(item.get('title', ''))}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _normalize_key_str(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().replace("**", "").replace("`", "")).strip()
