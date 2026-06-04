from __future__ import annotations

from pathlib import Path

from app.infrastructure.services.repository import repository_analysis
from app.infrastructure.services.repository.repository_analysis import collect_files_with_stats
from app.infrastructure.services.scan.segmentation_planning import build_scan_work_units
from app.infrastructure.services.scan.scan_execution_service import (
    attach_path_context,
    merge_validated_findings,
    promote_cross_file_candidates,
)


def test_collect_files_skips_heavy_and_test_directories(tmp_path: Path) -> None:
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.py").write_text("print('ignored')", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text("def login(): pass", encoding="utf-8")
    (tmp_path / "src" / "tests").mkdir()
    (tmp_path / "src" / "tests" / "test_auth.py").write_text("def test_login(): pass", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    result = collect_files_with_stats(tmp_path, "folder")
    relative_files = {path.relative_to(tmp_path).as_posix() for path in result.files}

    assert "package.json" in relative_files
    assert "src/auth.py" in relative_files
    assert "node_modules/ignored.py" not in relative_files
    assert "src/tests/test_auth.py" not in relative_files
    assert result.stats.skipped_directories >= 1


def test_collect_files_caps_index_size(tmp_path: Path) -> None:
    for index in range(5):
        (tmp_path / f"service_{index}.py").write_text("def handler(): pass", encoding="utf-8")

    result = collect_files_with_stats(tmp_path, "folder", max_files=2)

    assert len(result.files) == 2
    assert result.stats.truncated is True


def test_read_text_uses_bounded_reads(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "large.py"
    target.write_text("a" * 128, encoding="utf-8")
    monkeypatch.setattr(repository_analysis, "MAX_FILE_READ_BYTES", 16)

    assert repository_analysis.read_text(target) == "a" * 16


def test_deep_scan_work_units_are_bounded(tmp_path: Path) -> None:
    files: list[Path] = []
    file_segments: list[dict] = []
    hotspot_files: list[dict] = []
    for file_index in range(260):
        path = tmp_path / f"service_{file_index}.py"
        path.write_text("def handler(): pass", encoding="utf-8")
        files.append(path)
        relative = path.relative_to(tmp_path).as_posix()
        hotspot_files.append({"file": relative, "score": 9, "reasons": ["request entrypoint"], "imports": []})
        file_segments.append(
            {
                "file": relative,
                "line_count": 1_000,
                "block_count": 10,
                "blocks": [
                    {
                        "block_id": f"{relative}:{block_index}",
                        "kind": "window",
                        "start_line": block_index * 10 + 1,
                        "end_line": block_index * 10 + 10,
                        "snippet": "request.body",
                    }
                    for block_index in range(10)
                ],
            }
        )

    work_units = build_scan_work_units(
        scan_mode="deep",
        files=files,
        source_root=tmp_path,
        repository_artifacts={"hotspot_files": hotspot_files},
        repository_map={"priority_paths": []},
        file_segments=file_segments,
        target_type="folder",
        traced_paths={"paths": []},
    )

    reviewed_files = {}
    for item in work_units["review_items"]:
        reviewed_files[item["file"]] = reviewed_files.get(item["file"], 0) + 1

    assert len(work_units["review_items"]) <= 1_200
    assert len(reviewed_files) <= 240
    assert max(reviewed_files.values()) <= 8


def test_heuristic_candidates_are_not_promoted_without_local_confirmation() -> None:
    heuristic_candidate = {
        "source": "heuristic",
        "severity": "high",
        "title": "Dynamic NoSQL query construction may allow operator injection",
        "file": "repositories/catalog/repository.py",
        "line": 42,
        "category": "NoSQL injection",
        "confidence": 95,
        "source_hint": "repositories/catalog/repository.py:10",
        "sink_hint": "repositories/catalog/repository.py:42",
        "path_hint": "repositories/catalog/repository.py",
    }

    assert merge_validated_findings([], [heuristic_candidate]) == []


def test_locally_confirmed_candidates_require_complete_path_proof() -> None:
    confirmed_candidate = {
        "source": "heuristic",
        "local_validation": "confirmed",
        "severity": "critical",
        "title": "User-controlled input reaches command execution",
        "file": "app.py",
        "line": 12,
        "category": "Command injection",
        "confidence": 92,
        "source_hint": "app.py:8",
        "sink_hint": "app.py:12",
        "path_hint": "app.py",
        "has_sanitizer": False,
    }

    assert merge_validated_findings([], [confirmed_candidate]) == [confirmed_candidate]


def test_path_context_requires_exact_sink_line_match() -> None:
    candidate = {
        "source": "heuristic",
        "file": "repositories/catalog/repository.py",
        "line": 50,
        "title": "Dynamic NoSQL query construction may allow operator injection",
    }
    traced_paths = {
        "paths": [
            {
                "source": {"file": "repositories/catalog/repository.py", "line": 10},
                "sink": {"file": "repositories/catalog/repository.py", "line": 20},
                "path_hint": "repositories/catalog/repository.py",
                "line_sequence": [10, 20],
                "has_sanitizer": False,
                "confidence": 88,
            }
        ]
    }

    assert attach_path_context([candidate], traced_paths)[0] == candidate


def test_cross_file_promotion_does_not_bypass_validation_for_heuristics(tmp_path: Path) -> None:
    target = tmp_path / "repo.py"
    target.write_text("\n".join(f"line_{index}" for index in range(1, 20)), encoding="utf-8")
    candidate = {
        "source": "heuristic",
        "severity": "high",
        "title": "Dynamic query construction may allow injection",
        "file": "repo.py",
        "line": 12,
        "category": "SQL injection",
        "confidence": 95,
        "source_hint": "api.py:3",
        "sink_hint": "repo.py:12",
        "path_hint": "api.py -> repo.py",
        "path_line_sequence": [3, 12],
        "has_sanitizer": False,
    }
    traced_paths = {
        "paths": [
            {
                "source": {"file": "api.py", "line": 3},
                "sink": {"file": "repo.py", "line": 12},
                "path_hint": "api.py -> repo.py",
                "path_type": "cross_file",
                "has_sanitizer": False,
            }
        ]
    }

    assert promote_cross_file_candidates([], [candidate], tmp_path, [target], traced_paths) == []
