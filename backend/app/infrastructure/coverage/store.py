from __future__ import annotations

import json
import os
import time

from app.infrastructure.coverage.models import CoverageEntry, CoverageSummary


def _key_of(endpoint: str, param: str, vuln_class: str) -> str:
    return f"{endpoint}\x00{param}\x00{vuln_class}"


def _normalize_endpoint(s: str) -> str:
    trimmed = s.strip()
    q = trimmed.find("?")
    return trimmed[:q] if q >= 0 else trimmed


class CoverageStore:
    def __init__(self, path: str):
        self._path = os.path.abspath(path)
        self._entries: dict[str, CoverageEntry] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict) or data.get("version") != 1:
                return
            for e in data.get("entries", []):
                if self._is_valid_entry(e):
                    entry = CoverageEntry(**e)
                    self._entries[_key_of(entry.endpoint, entry.param, entry.vuln_class)] = entry
        except (json.JSONDecodeError, OSError):
            pass

    def mark(self, endpoint: str, param: str, vuln_class: str, status: str = "tried", notes: str | None = None) -> CoverageEntry:
        self.load()
        ep = _normalize_endpoint(endpoint)
        param = param.strip()
        vc = vuln_class.strip().lower()
        if not ep or not param or not vc:
            raise ValueError("endpoint, param, and vuln_class are all required")
        key = _key_of(ep, param, vc)
        now = time.time()
        prev = self._entries.get(key)
        entry = CoverageEntry(
            endpoint=ep,
            param=param,
            vuln_class=vc,
            status=status,
            count=(prev.count if prev else 0) + 1,
            first_seen=prev.first_seen if prev else now,
            last_seen=now,
            notes=notes or (prev.notes if prev else None),
        )
        self._entries[key] = entry
        self._save()
        return entry

    def list(self, endpoint: str | None = None, param: str | None = None, vuln_class: str | None = None, status: str | None = None) -> list[CoverageEntry]:
        self.load()
        all_entries = sorted(self._entries.values(), key=lambda e: e.last_seen)
        if not endpoint and not param and not vuln_class and not status:
            return all_entries
        result = []
        for e in all_entries:
            if endpoint and endpoint not in e.endpoint:
                continue
            if param and e.param != param:
                continue
            if vuln_class and e.vuln_class != vuln_class.lower():
                continue
            if status and e.status != status:
                continue
            result.append(e)
        return result

    def untested(self, candidates: list[dict], vuln_classes: list[str]) -> list[dict]:
        self.load()
        result = []
        for c in candidates:
            ep = _normalize_endpoint(c.get("endpoint", ""))
            param = c.get("param", "").strip()
            for v in vuln_classes:
                key = _key_of(ep, param, v.lower())
                if key not in self._entries:
                    result.append({"endpoint": ep, "param": param, "vuln_class": v.lower()})
        return result

    def summary(self) -> CoverageSummary:
        self.load()
        by_status: dict[str, int] = {}
        by_vuln_class: dict[str, int] = {}
        for e in self._entries.values():
            by_status[e.status] = by_status.get(e.status, 0) + 1
            by_vuln_class[e.vuln_class] = by_vuln_class.get(e.vuln_class, 0) + 1
        return CoverageSummary(
            total=len(self._entries),
            by_status=by_status,
            by_vuln_class=by_vuln_class,
        )

    def clear(self) -> None:
        self.load()
        self._entries.clear()
        self._save()

    def _save(self) -> None:
        directory = os.path.dirname(self._path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        payload = {
            "version": 1,
            "entries": [e.model_dump() for e in self._entries.values()],
        }
        with open(self._path, "w") as f:
            json.dump(payload, f, indent=2)

    @staticmethod
    def _is_valid_entry(e: dict) -> bool:
        required = {"endpoint", "param", "vuln_class", "status", "count", "first_seen", "last_seen"}
        return all(k in e and isinstance(e[k], (str, int, float)) for k in required)
