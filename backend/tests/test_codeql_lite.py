from __future__ import annotations

from pathlib import Path

from app.infrastructure.services.repository.codeql_lite import (
    build_program_database,
    run_codeql_lite_queries,
)


def test_program_database_builds_nodes_and_edges(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text(
        """
def handler(public_key):
    query = {"device_public_key": public_key}
    return db.devices.find_one(query)
""".strip(),
        encoding="utf-8",
    )

    program = build_program_database(tmp_path, [target])

    assert program.to_dict()["summary"]["functions"] == 1
    assert program.to_dict()["summary"]["cfg_nodes"] >= 2
    assert any(node.kind == "function" and node.name == "handler" for node in program.nodes)
    assert any(edge.kind == "CONTAINS" for edge in program.edges)
    assert any(edge.kind == "CFG_NEXT" for edge in program.edges)


def test_program_database_builds_branch_and_loop_cfg(tmp_path: Path) -> None:
    target = tmp_path / "flow.py"
    target.write_text(
        """
def handler(public_key, enabled):
    if enabled:
        value = public_key
    else:
        value = "safe"
    while enabled:
        break
    return value
""".strip(),
        encoding="utf-8",
    )

    program = build_program_database(tmp_path, [target])
    function = next(iter(program.functions.values()))

    edge_kinds = {edge.kind for edge in function.cfg_edges}
    assert {"true", "false", "loop", "back"} <= edge_kinds


def test_codeql_lite_finds_python_mongo_source_to_sink(tmp_path: Path) -> None:
    target = tmp_path / "security_repository.py"
    target.write_text(
        """
class SecurityRepository:
    def get_by_public_key_for_user(self, user_id: str, public_key: dict):
        query = {"user_id": user_id, "device_public_key": public_key}
        return self.collection.find_one(query)
""".strip(),
        encoding="utf-8",
    )

    program = build_program_database(tmp_path, [target])
    findings = run_codeql_lite_queries(program)

    assert [finding["category"] for finding in findings] == ["NoSQL injection"]
    assert findings[0]["source"] == "codeql_lite"
    assert findings[0]["query_id"] == "py/mongo-operator-injection"
    assert findings[0]["local_validation"] == "confirmed"
    assert findings[0]["confidence"] >= 90
    assert findings[0]["path_nodes"]
    assert findings[0]["exploitability"] == "operator_payload_reaches_filter"
    assert findings[0]["ai_validation_context"]["query_id"] == "py/mongo-operator-injection"
    assert findings[0]["fix_suggestions"]


def test_codeql_lite_tracks_interprocedural_flow(tmp_path: Path) -> None:
    target = tmp_path / "routes.py"
    target.write_text(
        """
def route_handler(public_key):
    return lookup_device(public_key)

def lookup_device(key):
    return devices.find_one({"device_public_key": key})
""".strip(),
        encoding="utf-8",
    )

    program = build_program_database(tmp_path, [target])
    findings = run_codeql_lite_queries(program)

    assert len(findings) == 1
    assert findings[0]["sink_hint"] == "routes.py:5"
    assert "route_handler -> lookup_device" in findings[0]["path_hint"]
    assert findings[0]["confidence"] >= 95


def test_codeql_lite_does_not_flag_sanitized_regex_query(tmp_path: Path) -> None:
    target = tmp_path / "catalog_repository.py"
    target.write_text(
        """
import re

def search_products(search: str):
    query = {"name": {"$regex": re.escape(search), "$options": "i"}}
    return products.find(query)
""".strip(),
        encoding="utf-8",
    )

    program = build_program_database(tmp_path, [target])

    assert run_codeql_lite_queries(program) == []


def test_codeql_lite_sanitizer_cancels_taint(tmp_path: Path) -> None:
    target = tmp_path / "security_repository.py"
    target.write_text(
        """
def handler(public_key):
    safe_key = validate(public_key)
    return devices.find_one({"device_public_key": safe_key})
""".strip(),
        encoding="utf-8",
    )

    program = build_program_database(tmp_path, [target])

    assert run_codeql_lite_queries(program) == []


def test_codeql_lite_does_not_flag_safe_update_set_payload(tmp_path: Path) -> None:
    target = tmp_path / "sync.py"
    target.write_text(
        """
def update_status(sync_id: str, fields: dict[str, str]):
    return statuses.update_one({"id": sync_id}, {"$set": fields})
""".strip(),
        encoding="utf-8",
    )

    program = build_program_database(tmp_path, [target])

    assert run_codeql_lite_queries(program) == []


def test_codeql_lite_does_not_flag_update_document_only_taint(tmp_path: Path) -> None:
    target = tmp_path / "sync.py"
    target.write_text(
        """
def update_status(fields):
    return statuses.update_one({"id": "fixed"}, {"$set": fields})
""".strip(),
        encoding="utf-8",
    )

    program = build_program_database(tmp_path, [target])

    assert run_codeql_lite_queries(program) == []
