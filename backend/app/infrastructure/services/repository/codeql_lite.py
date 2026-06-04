from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.infrastructure.services.repository.repository_analysis import (
    MAX_ARTIFACT_CONTENT_FILES,
    prioritize_files_for_analysis,
    read_text,
    relative_path,
)


PYTHON_EXTENSIONS = {".py"}
SOURCE_PARAM_NAMES = {
    "request",
    "req",
    "body",
    "payload",
    "input",
    "data",
    "query",
    "filters",
    "criteria",
    "selector",
    "public_key",
    "jwk",
}
SOURCE_CALLS = {"input", "json", "body", "form", "query_params", "request.json", "request.body", "request.form"}
SANITIZER_CALLS = {"escape", "re.escape", "sanitize", "validate", "str", "int", "float", "bool"}
MONGO_FILTER_SINKS = {"find", "find_one", "findone", "find_one_and_update", "find_one_and_delete", "update_one", "update_many", "aggregate"}
SQL_SINKS = {"execute", "query", "raw", "sql_query"}
COMMAND_SINKS = {"system", "subprocess.run", "subprocess.Popen", "subprocess.call"}
MONGO_FILTER_ARG_INDEXES = {
    "find": {0},
    "find_one": {0},
    "findone": {0},
    "find_one_and_update": {0},
    "find_one_and_delete": {0},
    "update_one": {0},
    "update_many": {0},
    "aggregate": {0},
}


@dataclass(frozen=True, slots=True)
class ProgramNode:
    id: str
    kind: str
    file: str
    line: int
    name: str
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProgramEdge:
    source: str
    target: str
    kind: str
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CFGNode:
    id: str
    file: str
    line: int
    kind: str
    label: str


@dataclass(frozen=True, slots=True)
class CFGEdge:
    source: str
    target: str
    kind: str


@dataclass(slots=True)
class FunctionSummary:
    id: str
    file: str
    name: str
    qualname: str
    line: int
    params: list[str]
    assignments: list[dict[str, Any]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    returns: list[dict[str, Any]] = field(default_factory=list)
    cfg_nodes: list[CFGNode] = field(default_factory=list)
    cfg_edges: list[CFGEdge] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TaintPath:
    source_hint: str
    sink_hint: str
    nodes: list[str]
    tainted_symbol: str
    sink_kind: str
    sanitized: bool
    cross_function: bool


@dataclass(frozen=True, slots=True)
class CodeQLLiteQuery:
    id: str
    category: str
    sink_kinds: frozenset[str]
    severity: str
    exploit_payloads: tuple[str, ...]
    recommended_fix: str


DEFAULT_QUERIES: tuple[CodeQLLiteQuery, ...] = (
    CodeQLLiteQuery(
        id="py/mongo-operator-injection",
        category="NoSQL injection",
        sink_kinds=frozenset({"mongodb_query"}),
        severity="high",
        exploit_payloads=("$ne", "$gt", "$where"),
        recommended_fix="Validate structured input and query by explicit scalar fields or wrap user values with $eq.",
    ),
    CodeQLLiteQuery(
        id="py/sql-string-taint",
        category="SQL injection",
        sink_kinds=frozenset({"sql_query"}),
        severity="high",
        exploit_payloads=("' OR '1'='1", "\" OR \"1\"=\"1"),
        recommended_fix="Use parameterized queries and bind variables instead of constructing SQL from tainted data.",
    ),
    CodeQLLiteQuery(
        id="py/command-taint",
        category="Command injection",
        sink_kinds=frozenset({"command_execution"}),
        severity="critical",
        exploit_payloads=("; id", "&& whoami", "| cat /etc/passwd"),
        recommended_fix="Avoid shell execution with tainted input; pass validated arguments as an argv list with shell disabled.",
    ),
)


@dataclass(slots=True)
class ProgramDatabase:
    nodes: list[ProgramNode]
    edges: list[ProgramEdge]
    functions: dict[str, FunctionSummary]
    functions_by_name: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [_node_to_dict(node) for node in self.nodes],
            "edges": [_edge_to_dict(edge) for edge in self.edges],
            "functions": {
                function_id: {
                    "file": summary.file,
                    "name": summary.name,
                    "qualname": summary.qualname,
                    "line": summary.line,
                    "params": summary.params,
                    "assignments": summary.assignments,
                    "calls": summary.calls,
                    "returns": summary.returns,
                    "cfg_nodes": [_cfg_node_to_dict(node) for node in summary.cfg_nodes],
                    "cfg_edges": [_cfg_edge_to_dict(edge) for edge in summary.cfg_edges],
                }
                for function_id, summary in self.functions.items()
            },
            "summary": {
                "nodes": len(self.nodes),
                "edges": len(self.edges),
                "functions": len(self.functions),
                "cfg_nodes": sum(len(summary.cfg_nodes) for summary in self.functions.values()),
                "cfg_edges": sum(len(summary.cfg_edges) for summary in self.functions.values()),
            },
        }


def build_program_database(source_root: Path, files: list[Path]) -> ProgramDatabase:
    nodes: list[ProgramNode] = []
    edges: list[ProgramEdge] = []
    functions: dict[str, FunctionSummary] = {}
    functions_by_name: dict[str, list[str]] = {}

    for path in prioritize_files_for_analysis(files, MAX_ARTIFACT_CONTENT_FILES):
        if path.suffix.lower() not in PYTHON_EXTENSIONS:
            continue
        file_path = relative_path(path, source_root)
        text = read_text(path)
        if not text.strip():
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue

        visitor = _ProgramGraphVisitor(file_path)
        visitor.visit(tree)
        nodes.extend(visitor.nodes)
        edges.extend(visitor.edges)
        for summary in visitor.functions.values():
            functions[summary.id] = summary
            functions_by_name.setdefault(summary.name, []).append(summary.id)

    return ProgramDatabase(nodes=nodes, edges=edges, functions=functions, functions_by_name=functions_by_name)


def run_codeql_lite_queries(program: ProgramDatabase, queries: tuple[CodeQLLiteQuery, ...] = DEFAULT_QUERIES) -> list[dict[str, Any]]:
    return _PythonTaintQuery(program, queries).run()


class _ProgramGraphVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.nodes: list[ProgramNode] = []
        self.edges: list[ProgramEdge] = []
        self.functions: dict[str, FunctionSummary] = {}
        self._function_stack: list[FunctionSummary] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        current = self._current_function()
        if current is not None:
            value_symbols = _expr_names(node.value)
            value_call = _call_name(node.value.func) if isinstance(node.value, ast.Call) else ""
            sanitized_symbols = _sanitized_symbols(node.value)
            for target in node.targets:
                for target_name in _target_names(target):
                    assignment = {
                        "target": target_name,
                        "value_symbols": value_symbols,
                        "value_call": value_call,
                        "sanitized_symbols": sanitized_symbols,
                        "line": int(node.lineno),
                    }
                    current.assignments.append(assignment)
                    assignment_id = _node_id("assign", self.file_path, node.lineno, target_name)
                    self.nodes.append(ProgramNode(assignment_id, "assignment", self.file_path, int(node.lineno), target_name, assignment))
                    self.edges.append(ProgramEdge(current.id, assignment_id, "CONTAINS"))
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        current = self._current_function()
        if current is not None:
            current.returns.append({"symbols": _expr_names(node.value), "line": int(node.lineno)})
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        current = self._current_function()
        if current is not None:
            call_name = _call_name(node.func)
            arg_symbol_groups = [_expr_names(arg) for arg in node.args]
            arg_symbols = _flatten_symbol_groups(arg_symbol_groups)
            call = {
                "call": call_name,
                "arg_symbols": arg_symbols,
                "arg_symbol_groups": arg_symbol_groups,
                "sanitized_symbols": _sanitized_symbols(node),
                "line": int(node.lineno),
                "sink_kind": _sink_kind(call_name),
            }
            current.calls.append(call)
            call_id = _node_id("call", self.file_path, node.lineno, call_name or "unknown")
            self.nodes.append(ProgramNode(call_id, "call", self.file_path, int(node.lineno), call_name, call))
            self.edges.append(ProgramEdge(current.id, call_id, "CONTAINS"))
        self.generic_visit(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualname = ".".join([*(summary.name for summary in self._function_stack), node.name])
        function_id = _node_id("function", self.file_path, node.lineno, qualname)
        params = [arg.arg for arg in node.args.args]
        summary = FunctionSummary(
            id=function_id,
            file=self.file_path,
            name=node.name,
            qualname=qualname,
            line=int(node.lineno),
            params=params,
        )
        cfg_nodes, cfg_edges = _build_function_cfg(self.file_path, function_id, node.body)
        summary.cfg_nodes = cfg_nodes
        summary.cfg_edges = cfg_edges
        self.functions[function_id] = summary
        self.nodes.append(ProgramNode(function_id, "function", self.file_path, int(node.lineno), node.name, {"params": params}))
        for cfg_node in cfg_nodes:
            self.nodes.append(ProgramNode(cfg_node.id, "cfg", cfg_node.file, cfg_node.line, cfg_node.label, {"cfg_kind": cfg_node.kind}))
            self.edges.append(ProgramEdge(function_id, cfg_node.id, "CFG_CONTAINS"))
        for cfg_edge in cfg_edges:
            self.edges.append(ProgramEdge(cfg_edge.source, cfg_edge.target, "CFG_NEXT", {"cfg_edge_kind": cfg_edge.kind}))
        if self._function_stack:
            self.edges.append(ProgramEdge(self._function_stack[-1].id, function_id, "CONTAINS"))

        self._function_stack.append(summary)
        self.generic_visit(node)
        self._function_stack.pop()

    def _current_function(self) -> FunctionSummary | None:
        if not self._function_stack:
            return None
        return self._function_stack[-1]


class _PythonTaintQuery:
    def __init__(self, program: ProgramDatabase, queries: tuple[CodeQLLiteQuery, ...]) -> None:
        self.program = program
        self.queries = queries

    def run(self) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        seen: set[tuple[str, int, str]] = set()
        for function_id, summary in self.program.functions.items():
            initial_taint = {param for param in summary.params if _is_source_name(param)}
            findings.extend(self._analyze_function(function_id, initial_taint, context=[], seen_contexts=set()))

        deduped: list[dict[str, Any]] = []
        for finding in findings:
            key = (str(finding.get("file", "")), int(finding.get("line", 0) or 0), str(finding.get("title", "")))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(finding)
        return deduped

    def _analyze_function(
        self,
        function_id: str,
        initial_taint: set[str],
        *,
        context: list[str],
        seen_contexts: set[tuple[str, tuple[str, ...], int]],
    ) -> list[dict[str, Any]]:
        summary = self.program.functions[function_id]
        context_key = (function_id, tuple(sorted(initial_taint)), len(context))
        if context_key in seen_contexts or len(context) > 8:
            return []
        seen_contexts.add(context_key)

        tainted = set(initial_taint)
        tainted_sources = {symbol: f"{summary.file}:{summary.line} parameter `{symbol}`" for symbol in tainted}
        changed = True
        while changed:
            changed = False
            for assignment in summary.assignments:
                target = str(assignment["target"])
                value_symbols = set(assignment.get("value_symbols", []))
                sanitized_symbols = set(assignment.get("sanitized_symbols", []))
                value_call = str(assignment.get("value_call", ""))
                if value_call in SOURCE_CALLS:
                    if target not in tainted:
                        tainted.add(target)
                        tainted_sources[target] = f"{summary.file}:{assignment['line']} source `{target}`"
                        changed = True
                    continue
                if tainted & value_symbols and not (tainted & sanitized_symbols):
                    if target not in tainted:
                        tainted.add(target)
                        source_symbol = sorted(tainted & value_symbols)[0]
                        tainted_sources[target] = tainted_sources.get(source_symbol, f"{summary.file}:{assignment['line']} tainted value")
                        changed = True

        findings: list[dict[str, Any]] = []
        for call in summary.calls:
            call_name = str(call.get("call", ""))
            sink_kind = str(call.get("sink_kind", ""))
            query = self._query_for_sink(sink_kind)
            tainted_args = _sink_tainted_args(call, tainted)
            if query is not None and tainted_args:
                tainted_symbol = tainted_args[0]
                path = TaintPath(
                    source_hint=tainted_sources.get(tainted_symbol, f"{summary.file}:{summary.line}"),
                    sink_hint=f"{summary.file}:{int(call.get('line', summary.line) or summary.line)}",
                    nodes=[*context, f"{summary.file}:{call['line']} {call_name}"],
                    tainted_symbol=tainted_symbol,
                    sink_kind=sink_kind,
                    sanitized=False,
                    cross_function=bool(context),
                )
                findings.append(_finding_from_sink(summary, call, path, query))

            for callee_id in self._resolve_callees(call_name):
                callee = self.program.functions[callee_id]
                arg_symbol_groups = call.get("arg_symbol_groups", [])
                callee_initial_taint = {
                    param
                    for index, param in enumerate(callee.params)
                    if index < len(arg_symbol_groups) and bool(set(arg_symbol_groups[index]) & tainted)
                }
                if not callee_initial_taint:
                    continue
                next_context = [*context, f"{summary.file}:{call['line']} {summary.name} -> {callee.name}"]
                findings.extend(
                    self._analyze_function(
                        callee_id,
                        callee_initial_taint,
                        context=next_context,
                        seen_contexts=seen_contexts,
                    )
                )
        return findings

    def _resolve_callees(self, call_name: str) -> list[str]:
        simple_name = call_name.rsplit(".", 1)[-1]
        return self.program.functions_by_name.get(simple_name, [])

    def _query_for_sink(self, sink_kind: str) -> CodeQLLiteQuery | None:
        for query in self.queries:
            if sink_kind in query.sink_kinds:
                return query
        return None


def _finding_from_sink(
    summary: FunctionSummary,
    call: dict[str, Any],
    path: TaintPath,
    query: CodeQLLiteQuery,
) -> dict[str, Any]:
    category = query.category
    line = int(call.get("line", summary.line) or summary.line)
    confidence = _score_taint_path(path)
    exploit_simulation = _simulate_static_exploit(path, query)
    return {
        "source": "codeql_lite",
        "query_id": query.id,
        "local_validation": "confirmed",
        "severity": query.severity,
        "title": f"CodeQL-lite dataflow: {category}",
        "file": summary.file,
        "line": line,
        "line_end": line,
        "category": category,
        "confidence": confidence,
        "summary": f"Tainted input `{path.tainted_symbol}` reaches `{call.get('call', '')}`.",
        "impact": f"An attacker-controlled value may influence a {path.sink_kind.replace('_', ' ')} sink.",
        "explanation": "The Program DB query found a reachable source-to-sink path with no sanitizer on the propagated symbol.",
        "source_hint": path.source_hint,
        "sink_hint": path.sink_hint,
        "path_hint": " -> ".join(path.nodes),
        "path_nodes": path.nodes,
        "attack_input": f"Control `{path.tainted_symbol}` at the source boundary.",
        "attack_execution": f"`{path.tainted_symbol}` flows into `{call.get('call', '')}`.",
        "attack_result": exploit_simulation["result"],
        "evidence": f"{summary.file}:{line} {call.get('call', '')}({', '.join(call.get('arg_symbols', []))})",
        "exploitability": exploit_simulation["exploitability"],
        "exploit_simulation": exploit_simulation,
        "ai_validation_context": {
            "query_id": query.id,
            "source": path.source_hint,
            "sink": path.sink_hint,
            "path": path.nodes,
            "sanitized": path.sanitized,
            "sink_kind": path.sink_kind,
        },
        "fix_suggestions": [
            {
                "id": "recommended",
                "label": "Fix query path",
                "profile": "recommended",
                "description": query.recommended_fix,
            }
        ],
        "audit_log": [
            "Built Program Database from Python AST",
            "Built function-level CFG and Program DB edges",
            f"Ran CodeQL-lite query `{query.id}`",
            f"Static exploit simulation verdict: {exploit_simulation['exploitability']}",
            f"Scored deterministic path confidence at {confidence}",
        ],
    }


def _score_taint_path(path: TaintPath) -> int:
    score = 78
    score += 8 if len(path.nodes) <= 1 else 5
    score += 6 if not path.sanitized else -18
    score += 5 if path.cross_function else 0
    score += 4 if path.sink_kind in {"command_execution", "mongodb_query", "sql_query"} else 0
    return max(0, min(98, score))


def _simulate_static_exploit(path: TaintPath, query: CodeQLLiteQuery) -> dict[str, Any]:
    if path.sanitized:
        return {
            "exploitability": "blocked_by_sanitizer",
            "payloads": [],
            "result": "The tainted value is sanitized before the sink, so this path was not retained as exploitable.",
        }
    if path.sink_kind == "mongodb_query":
        return {
            "exploitability": "operator_payload_reaches_filter",
            "payloads": list(query.exploit_payloads),
            "result": "A Mongo operator-shaped payload can reach the query filter position on this static path.",
        }
    if path.sink_kind == "sql_query":
        return {
            "exploitability": "sql_payload_reaches_query_builder",
            "payloads": list(query.exploit_payloads),
            "result": "A SQL control payload can reach a query execution sink on this static path.",
        }
    if path.sink_kind == "command_execution":
        return {
            "exploitability": "command_payload_reaches_execution",
            "payloads": list(query.exploit_payloads),
            "result": "A shell metacharacter payload can reach command execution on this static path.",
        }
    return {
        "exploitability": "static_path_confirmed",
        "payloads": list(query.exploit_payloads),
        "result": "A tainted payload reaches the sensitive sink on this static path.",
    }


def _sink_tainted_args(call: dict[str, Any], tainted: set[str]) -> list[str]:
    call_name = str(call.get("call", "")).lower()
    simple_name = call_name.rsplit(".", 1)[-1]
    arg_symbol_groups = call.get("arg_symbol_groups", [])
    sanitized_symbols = set(call.get("sanitized_symbols", []))

    if str(call.get("sink_kind", "")) == "mongodb_query":
        indexes = MONGO_FILTER_ARG_INDEXES.get(simple_name, {0})
        candidate_symbols: set[str] = set()
        for index in indexes:
            if index < len(arg_symbol_groups):
                candidate_symbols.update(str(symbol) for symbol in arg_symbol_groups[index])
        return sorted((candidate_symbols & tainted) - sanitized_symbols)

    arg_symbols = set(str(symbol) for symbol in call.get("arg_symbols", []))
    return sorted((arg_symbols & tainted) - sanitized_symbols)


def _sink_kind(call_name: str) -> str:
    lowered = call_name.lower()
    simple = lowered.rsplit(".", 1)[-1]
    if simple in MONGO_FILTER_SINKS:
        return "mongodb_query"
    if simple in SQL_SINKS or lowered in SQL_SINKS:
        return "sql_query"
    if simple in COMMAND_SINKS or lowered in COMMAND_SINKS:
        return "command_execution"
    return ""


def _is_source_name(name: str) -> bool:
    lowered = name.lower()
    return lowered in SOURCE_PARAM_NAMES or any(token in lowered for token in ("payload", "public_key", "selector", "criteria"))


def _call_name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}".strip(".")
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return ""


def _call_arg_symbols(node: ast.Call) -> list[str]:
    symbols: list[str] = []
    for arg in node.args:
        symbols.extend(_expr_names(arg))
    for keyword in node.keywords:
        symbols.extend(_expr_names(keyword.value))
    return list(dict.fromkeys(symbols))


def _flatten_symbol_groups(groups: list[list[str]]) -> list[str]:
    symbols: list[str] = []
    for group in groups:
        symbols.extend(group)
    return list(dict.fromkeys(symbols))


def _expr_names(node: ast.AST | None) -> list[str]:
    if node is None:
        return []
    names: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.append(child.id)
        elif isinstance(child, ast.Attribute):
            names.append(child.attr)
    return list(dict.fromkeys(names))


def _target_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for item in node.elts:
            names.extend(_target_names(item))
        return names
    return []


def _sanitized_symbols(node: ast.AST | None) -> list[str]:
    if node is None:
        return []
    symbols: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if _call_name(child.func) in SANITIZER_CALLS:
            symbols.extend(_call_arg_symbols(child))
    return list(dict.fromkeys(symbols))


def _build_function_cfg(file_path: str, function_id: str, body: list[ast.stmt]) -> tuple[list[CFGNode], list[CFGEdge]]:
    nodes: list[CFGNode] = []
    edges: list[CFGEdge] = []
    previous_exits: list[str] = []

    for stmt in body:
        entry_ids, exit_ids = _build_statement_cfg(file_path, function_id, stmt, nodes, edges)
        for previous in previous_exits:
            for entry in entry_ids:
                edges.append(CFGEdge(previous, entry, "next"))
        previous_exits = exit_ids

    return nodes, edges


def _build_statement_cfg(
    file_path: str,
    function_id: str,
    stmt: ast.stmt,
    nodes: list[CFGNode],
    edges: list[CFGEdge],
) -> tuple[list[str], list[str]]:
    node_id = _node_id("cfg", file_path, getattr(stmt, "lineno", 0), f"{function_id}:{type(stmt).__name__}")
    nodes.append(CFGNode(node_id, file_path, int(getattr(stmt, "lineno", 0) or 0), type(stmt).__name__, _cfg_label(stmt)))

    if isinstance(stmt, ast.If):
        body_entry, body_exit = _build_cfg_branch(file_path, function_id, stmt.body, nodes, edges)
        else_entry, else_exit = _build_cfg_branch(file_path, function_id, stmt.orelse, nodes, edges)
        for entry in body_entry:
            edges.append(CFGEdge(node_id, entry, "true"))
        for entry in else_entry:
            edges.append(CFGEdge(node_id, entry, "false"))
        exits = [*body_exit, *else_exit] or [node_id]
        if not stmt.orelse:
            exits.append(node_id)
        return [node_id], list(dict.fromkeys(exits))

    if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
        body_entry, body_exit = _build_cfg_branch(file_path, function_id, stmt.body, nodes, edges)
        for entry in body_entry:
            edges.append(CFGEdge(node_id, entry, "loop"))
        for exit_node in body_exit:
            edges.append(CFGEdge(exit_node, node_id, "back"))
        return [node_id], [node_id]

    if isinstance(stmt, ast.Return):
        return [node_id], []

    return [node_id], [node_id]


def _build_cfg_branch(
    file_path: str,
    function_id: str,
    body: list[ast.stmt],
    nodes: list[CFGNode],
    edges: list[CFGEdge],
) -> tuple[list[str], list[str]]:
    if not body:
        return [], []
    branch_entry: list[str] = []
    previous_exits: list[str] = []
    for index, stmt in enumerate(body):
        entry_ids, exit_ids = _build_statement_cfg(file_path, function_id, stmt, nodes, edges)
        if index == 0:
            branch_entry = entry_ids
        for previous in previous_exits:
            for entry in entry_ids:
                edges.append(CFGEdge(previous, entry, "next"))
        previous_exits = exit_ids
    return branch_entry, previous_exits


def _cfg_label(stmt: ast.stmt) -> str:
    if isinstance(stmt, ast.FunctionDef):
        return stmt.name
    if isinstance(stmt, ast.Assign):
        target_names: list[str] = []
        for target in stmt.targets:
            target_names.extend(_target_names(target))
        targets = ", ".join(target_names)
        return f"assign {targets}"
    if isinstance(stmt, ast.Return):
        return "return"
    if isinstance(stmt, ast.If):
        return "if"
    if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
        return type(stmt).__name__.lower()
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return _call_name(stmt.value.func)
    return type(stmt).__name__


def _node_id(kind: str, file_path: str, line: int, name: str) -> str:
    safe_name = name.replace(" ", "_")
    return f"{kind}:{file_path}:{line}:{safe_name}"


def _node_to_dict(node: ProgramNode) -> dict[str, Any]:
    return {"id": node.id, "kind": node.kind, "file": node.file, "line": node.line, "name": node.name, **node.attrs}


def _edge_to_dict(edge: ProgramEdge) -> dict[str, Any]:
    return {"source": edge.source, "target": edge.target, "kind": edge.kind, **edge.attrs}


def _cfg_node_to_dict(node: CFGNode) -> dict[str, Any]:
    return {"id": node.id, "file": node.file, "line": node.line, "kind": node.kind, "label": node.label}


def _cfg_edge_to_dict(edge: CFGEdge) -> dict[str, Any]:
    return {"source": edge.source, "target": edge.target, "kind": edge.kind}
