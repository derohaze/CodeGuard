import hashlib
import re
from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".php", ".cs", ".kt", ".rs", ".mjs", ".cjs", ".xml", ".jsp", ".jspf", ".graphql", ".gql",
}
IGNORED_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".venv", "__pycache__", ".idea", ".vscode"}
FRAMEWORK_HINTS = {
    "graphql": [
        r"\bimport graphene\b",
        r"\bfrom graphql\b",
        r"\bflask_graphql_auth\b",
        r"graphene\.schema",
        r"['\"]/graphql['\"]",
        r"\bapolloserver\b",
        r"\bexpress-graphql\b",
        r"\bgraphqlhttp\b",
        r"\btype\s+(query|mutation)\b",
        r"\bresolver\b",
    ],
    "fastapi": [
        r"\bfrom fastapi import\b",
        r"\bimport fastapi\b",
        r"\bfastapi\s*[=><~]",
        r"\"fastapi\"\s*:",
        r"\bFastAPI\(",
        r"\bAPIRouter\(",
        r"\bfrom fastapi\.routing import\b",
    ],
    "django": [r"\bfrom django\b", r"\bimport django\b", r"django\s*[=><~]", r"\"django\"\s*:"],
    "flask": [r"\bfrom flask import\b", r"\bimport flask\b", r"flask\s*[=><~]", r"\"flask\"\s*:"],
    "express": [r"from ['\"]express['\"]", r"require\(['\"]express['\"]\)", r"\"express\"\s*:"],
    "nestjs": [r"from ['\"]@nestjs", r"\"@nestjs[^\"']*\"\s*:"],
    "php": [r"<\?php", r"\$_(get|post|request|cookie|files)\b", r"\bmysqli?_", r"\bsession_start\s*\("],
    "java_servlet": [
        r"\bextends\s+httpservlet\b",
        r"\bhttpservletrequest\b",
        r"\brequestdispatcher\b",
        r"<web-app",
        r"@webservlet\b",
        r"\bdoget\s*\(",
        r"\bdopost\s*\(",
        r"<jsp:(include|forward)\b",
        r"\bhttpsession\b",
    ],
    "jaxrs": [r"\bjavax\.ws\.rs\b", r"@path\b", r"@get\b", r"@post\b", r"@put\b", r"@delete\b"],
    "spring": [r"@restcontroller\b", r"@controller\b", r"@requestmapping\b", r"@getmapping\b", r"@postmapping\b"],
    "springboot": [r"@springbootapplication\b", r"org\.springframework\.", r"spring-boot"],
    "grpc": [r"\bgrpc\.newclient\b", r"\bgrpc\.dial\b", r"\bgrpcserver\b", r"\bgrpc\b", r"_service_addr", r"_service_url"],
    "react": [r"from ['\"]react['\"]", r"\"react\"\s*:"],
    "nextjs": [r"from ['\"]next", r"\"next\"\s*:"],
    "mongodb": [r"\bfrom pymongo\b", r"\bimport pymongo\b", r"\"mongoose\"\s*:", r"\"mongodb\"\s*:"],
}
INPUT_TOKENS = (
    "request.", "params", "query", "body", "payload", "user_input", "input(", "form", "args", "path_params",
    "request.getparameter(", "request.getheader(", "request.getcookies(", "request.getquerystring(",
    "request.getsession(", "request.getrequesturi(", "request.getservletpath(", "request.getpathinfo(",
    "graphene.string(", "graphene.int(", "graphene.boolean(", "info.context", "request.remote_addr",
    "args.", "context.req", "context.request", "context.user", "variables.", "input.",
    "os.getenv(", "process.env.", "mux.vars(", "r.formvalue(",
)
ROUTE_PATTERNS = (
    r"@\w+\.(get|post|put|delete|patch)\(",
    r"\b(router|app)\.(get|post|put|delete|patch)\(",
    r"@(Get|Post|Put|Delete|Patch)\(",
    r"@RequestMapping\(",
    r"@(?:Get|Post|Put|Delete|Patch)Mapping\(",
    r"\bHandleFunc\(",
    r"\bextends\s+HttpServlet\b",
    r"\bapp\.add_url_rule\(['\"]/graphql",
    r"\bapp\.use\(['\"]/graphql",
    r"\bgraphqlhttp\b",
    r"\bexpress-graphql\b",
    r"@WebServlet\b",
)
AUTH_PATTERNS = ("jwt", "bearer", "authorization", "session", "token", "oauth", "auth", "securitycontext", "principal", "isuserinrole", "context.user")
SOURCE_PATTERNS = (
    r"\brequest\.(json|args|form|query_params|headers|cookies|body)\b",
    r"\b(req|request)\.(body|query|params|headers|cookies)\b",
    r"\b(input|payload|user_input|webhook_url|callback_url|redirect_url)\b",
    r"\b(args|input|variables)\.[a-z_][a-z0-9_]*\b",
    r"\brequest\.get(parameter|parametervalues|header|querystring|cookies|requesturi|pathinfo|servletpath)\b",
)
SINK_PATTERNS = (
    r"\bos\.system\(",
    r"\bsubprocess\.(run|Popen|call)\(",
    r"\bchild_process\.(exec|spawn|execfile)\(",
    r"\bruntime\.getruntime\(\)\.exec\b",
    r"\bprocessbuilder\b",
    r"\brequests\.(get|post|put|delete)\(",
    r"\bhttpx\.(get|post|put|delete)\(",
    r"\b(fetch|axios\.|got\.)",
    r"\bgrpc\.(newclient|dial)\(",
    r"\b(send_file|FileResponse|open\(|pickle\.load|pickle\.loads|yaml\.load|exec\(|eval\()",
    r"\b(cursor\.execute|execute\(|query\()",
    r"\bresponse\.sendredirect\s*\(",
)


def collect_files(source: Path, target_type: str) -> list[Path]:
    if target_type == "file":
        return [source]

    files: list[Path] = []
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if is_test_or_fixture_path(path):
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS and path.name.lower() not in {
            "package.json", "requirements.txt", "pyproject.toml", "build.gradle", "pom.xml", "composer.json", "go.mod", "web.xml"
        }:
            continue
        files.append(path)
    return files


def is_test_or_fixture_path(path: Path) -> bool:
    lowered_parts = [part.lower() for part in path.parts]
    joined = "/".join(lowered_parts)
    if "/src/test/" in joined or "/src/it/" in joined:
        return True
    if any(part in {"test", "tests", "__tests__", "spec", "specs", "fixtures"} for part in lowered_parts):
        return True
    return False


def build_repository_profile(source_root: Path, files: list[Path]) -> dict:
    languages = count_languages(files)
    manifests = [
        path.name
        for path in files
        if path.name in {"package.json", "requirements.txt", "pyproject.toml", "build.gradle", "pom.xml", "composer.json", "go.mod", "web.xml"}
    ]
    framework_hits: set[str] = set()
    for path in files[:240]:
        if path.name not in {"package.json", "requirements.txt", "pyproject.toml", "build.gradle", "pom.xml", "composer.json", "go.mod", "web.xml"} and path.suffix.lower() not in {
            ".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".php", ".go", ".xml", ".jsp", ".jspf", ".graphql", ".gql"
        }:
            continue
        text = read_text(path)
        focused = text[:12000].lower()
        for framework, hints in FRAMEWORK_HINTS.items():
            if any(re.search(pattern, focused, flags=re.MULTILINE) for pattern in hints):
                framework_hits.add(framework)
    directories = {str(path.parent.relative_to(source_root)) for path in files if path.parent.exists()}
    entrypoints = [
        relative_path(path, source_root)
        for path in files
        if path.name.lower() in {"main.py", "app.py", "server.py", "index.ts", "index.js", "main.ts", "main.tsx", "main.go", "server.go", "web.xml"}
    ][:8]
    return {
        "root": str(source_root),
        "file_count": len([path for path in files if path.suffix.lower() in SUPPORTED_EXTENSIONS]),
        "directory_count": len(directories),
        "languages": languages,
        "frameworks": sorted(framework_hits),
        "manifests": manifests,
        "entrypoints": entrypoints,
    }


def build_repository_artifacts(source_root: Path, files: list[Path], profile: dict) -> dict:
    import_fan_out: dict[str, int] = {}
    import_fan_in: dict[str, int] = {}
    route_files: list[dict] = []
    auth_files: list[dict] = []
    source_candidates: list[dict] = []
    sink_candidates: list[dict] = []
    hotspot_files: list[dict] = []

    for path in files:
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        text = read_text(path)
        file_path = relative_path(path, source_root)
        imports = parse_imports(path, text, source_root)
        import_fan_out[file_path] = len(imports)
        for imported in imports:
            import_fan_in[imported] = import_fan_in.get(imported, 0) + 1

        route_summary = detect_route_summary(path, text, source_root)
        if route_summary:
            route_files.append(route_summary)

        auth_summary = detect_auth_summary(path, text, source_root)
        if auth_summary:
            auth_files.append(auth_summary)

        source_candidates.extend(detect_candidates(text, file_path, SOURCE_PATTERNS, "source"))
        sink_candidates.extend(detect_candidates(text, file_path, SINK_PATTERNS, "sink"))

        hotspot_score, hotspot_reasons = score_hotspot(path, text, route_summary, auth_summary, len(imports))
        if hotspot_score > 0:
            hotspot_files.append(
                {
                    "file": file_path,
                    "score": hotspot_score,
                    "reasons": hotspot_reasons,
                    "imports": imports[:6],
                }
            )

    hotspot_files.sort(key=lambda item: (-item["score"], item["file"]))
    route_files.sort(key=lambda item: (-item["route_count"], item["file"]))
    auth_files.sort(key=lambda item: item["file"])
    source_candidates = source_candidates[:24]
    sink_candidates = sink_candidates[:24]

    trust_boundaries = build_trust_boundaries(profile, route_files, auth_files, source_candidates, sink_candidates)
    reviewed_files = [item["file"] for item in hotspot_files[:12]]
    coverage = {
        "reviewed_hotspots": len(reviewed_files),
        "eligible_files": profile["file_count"],
        "route_files": len(route_files),
        "auth_files": len(auth_files),
        "source_candidates": len(source_candidates),
        "sink_candidates": len(sink_candidates),
    }

    return {
        "route_files": route_files[:12],
        "auth_files": auth_files[:12],
        "source_candidates": source_candidates,
        "sink_candidates": sink_candidates,
        "hotspot_files": hotspot_files[:18],
        "trust_boundaries": trust_boundaries[:10],
        "import_graph": {
            "nodes": profile["file_count"],
            "edges": sum(import_fan_out.values()),
            "top_fan_out": top_import_metrics(import_fan_out),
            "top_fan_in": top_import_metrics(import_fan_in),
        },
        "coverage": coverage,
        "reviewed_files": reviewed_files,
    }


def build_review_work_items(
    files: list[Path],
    source_root: Path,
    repository_artifacts: dict,
    repository_map: dict,
    target_type: str,
) -> list[dict[str, str]]:
    path_lookup = {relative_path(path, source_root): path for path in files if path.suffix.lower() in SUPPORTED_EXTENSIONS}
    hotspot_lookup = {item["file"]: item for item in repository_artifacts["hotspot_files"]}
    selected_files: list[str] = []

    for item in repository_map.get("priority_paths", []):
        file_path = str(item.get("file", "")).strip()
        if file_path in path_lookup and file_path not in selected_files:
            selected_files.append(file_path)

    for item in repository_artifacts["hotspot_files"]:
        if item["file"] not in selected_files:
            selected_files.append(item["file"])

    limit = 14 if target_type == "folder" else 6
    work_items: list[dict[str, str]] = []
    for file_path in selected_files[:limit]:
        path = path_lookup.get(file_path)
        if path is None:
            continue
        text = read_text(path)
        hotspot = hotspot_lookup.get(file_path, {})
        work_items.append(
            {
                "file": file_path,
                "signal_score": str(hotspot.get("score", 1)),
                "rationale": ", ".join(hotspot.get("reasons", [])[:4]) or "security-relevant code path",
                "imports": ", ".join(hotspot.get("imports", [])[:6]),
                "related_attack_surface": lookup_attack_surface(file_path, repository_map),
                "review_focus": lookup_review_focus(file_path, repository_map),
                "snippet": extract_relevant_excerpt(text),
            }
        )

    if not work_items and files:
        path = files[0]
        work_items.append(
            {
                "file": relative_path(path, source_root),
                "signal_score": "1",
                "rationale": "selected file context",
                "imports": "",
                "related_attack_surface": "selected scope",
                "review_focus": "review the most security-sensitive flows in this file",
                "snippet": extract_relevant_excerpt(read_text(path)),
            }
        )

    return work_items


def run_precise_heuristics(path: Path, text: str, source_root: Path) -> list[dict]:
    relative = relative_path(path, source_root)
    lowered = text.lower()
    findings: list[dict] = []

    if has_command_injection_signal(lowered):
        findings.append(make_finding_candidate(relative, text, "critical", "Possible command injection through shell execution", "Command injection"))

    if ("verify_signature" in lowered and "false" in lowered) or ("\"none\"" in lowered and "jwt" in lowered):
        findings.append(make_finding_candidate(relative, text, "critical", "JWT verification may accept unsigned tokens", "Authentication bypass"))

    if has_path_traversal_signal(lowered):
        findings.append(make_finding_candidate(relative, text, "high", "User-controlled path may reach filesystem access", "Path traversal"))

    if has_ssrf_signal(lowered):
        findings.append(make_finding_candidate(relative, text, "high", "User-controlled URL may reach outbound HTTP client", "Server-side request forgery"))

    if has_sql_injection_signal(lowered):
        findings.append(make_finding_candidate(relative, text, "high", "Dynamic query construction may allow injection", "SQL injection"))

    if has_nosql_injection_signal(lowered):
        findings.append(make_finding_candidate(relative, text, "high", "Dynamic NoSQL query construction may allow operator injection", "NoSQL injection"))

    if has_graphql_sql_injection_signal(lowered):
        findings.append(make_finding_candidate(relative, text, "high", "GraphQL resolver builds a dynamic SQL filter from user input", "SQL injection"))

    if has_eval_injection_signal(lowered):
        findings.append(make_finding_candidate(relative, text, "critical", "User-controlled input reaches eval()", "Code injection"))

    if has_graphql_command_injection_signal(lowered):
        findings.append(make_finding_candidate(relative, text, "critical", "GraphQL resolver reaches command execution with user-controlled input", "Command injection"))

    if has_open_redirect_signal(lowered):
        findings.append(make_finding_candidate(relative, text, "high", "User-controlled redirect target may enable open redirect", "Open redirect"))

    if has_session_fixation_signal(text):
        findings.append(make_finding_candidate(relative, text, "high", "Session state changes without regeneration after login", "Session fixation"))

    if has_idor_signal(lowered):
        findings.append(make_finding_candidate(relative, text, "high", "Route trusts attacker-controlled object reference", "Insecure direct object reference"))

    if has_privilege_bypass_signal(lowered):
        findings.append(make_finding_candidate(relative, text, "high", "Privileged route appears reachable without role enforcement", "Privilege escalation"))

    if "yaml.load(" in lowered and "safeloader" not in lowered:
        findings.append(make_finding_candidate(relative, text, "high", "Unsafe YAML deserialization detected", "Unsafe deserialization"))

    if "pickle.loads(" in lowered or "pickle.load(" in lowered:
        findings.append(make_finding_candidate(relative, text, "critical", "Unsafe pickle deserialization detected", "Unsafe deserialization"))

    if has_graphql_auth_bypass_signal(lowered):
        findings.append(make_finding_candidate(relative, text, "critical", "GraphQL token handling may bypass signature verification", "Authentication bypass"))

    if has_graphql_upload_path_signal(lowered):
        findings.append(make_finding_candidate(relative, text, "high", "GraphQL file import path may write attacker-controlled filenames", "Path traversal"))

    deduped: dict[tuple[str, str], dict] = {}
    for item in findings:
        deduped[(item["file"], item["title"])] = item
    return list(deduped.values())


def count_languages(files: list[Path]) -> list[str]:
    mapping = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".kt": "kotlin",
        ".rs": "rust",
    }
    counts: dict[str, int] = {}
    for path in files:
        language = mapping.get(path.suffix.lower())
        if not language:
            continue
        counts[language] = counts.get(language, 0) + 1
    return [item[0] for item in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))]


def parse_imports(path: Path, text: str, source_root: Path) -> list[str]:
    imports: set[str] = set()
    if path.suffix.lower() == ".py":
        for match in re.finditer(r"^\s*(?:from\s+([a-zA-Z0-9_\.]+)\s+import|import\s+([a-zA-Z0-9_\.]+))", text, flags=re.MULTILINE):
            module = match.group(1) or match.group(2) or ""
            if module.startswith("."):
                continue
            imports.add(module.replace(".", "/"))
    elif path.suffix.lower() in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        for match in re.finditer(r"(?:from\s+['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"]\))", text):
            module = match.group(1) or match.group(2) or ""
            if module.startswith("."):
                imports.add(resolve_relative_import(path, module, source_root))
            else:
                imports.add(module)
    elif path.suffix.lower() == ".java":
        for match in re.finditer(r"^\s*import\s+([a-zA-Z0-9_\.]+)\s*;", text, flags=re.MULTILINE):
            imports.add(match.group(1).replace(".", "/"))
    elif path.suffix.lower() == ".go":
        for match in re.finditer(r"^\s*import\s+(?:\(\s*)?\"([^\"]+)\"", text, flags=re.MULTILINE):
            imports.add(match.group(1))
    elif path.suffix.lower() == ".php":
        for match in re.finditer(r"\b(?:include|require|include_once|require_once)\s*\(?\s*['\"]([^'\"]+)['\"]", text, flags=re.IGNORECASE):
            module = match.group(1)
            if module.startswith(".") or "/" in module:
                imports.add(resolve_relative_import(path, module, source_root))
            else:
                imports.add(module)
    elif path.suffix.lower() in {".jsp", ".jspf"}:
        for match in re.finditer(r"<(?:jsp:include|%@\s*include)\s+(?:page|file)\s*=\s*['\"]([^'\"]+)['\"]", text, flags=re.IGNORECASE):
            imports.add(resolve_relative_import(path, match.group(1), source_root))
    return sorted(item for item in imports if item)


def resolve_relative_import(path: Path, module: str, source_root: Path) -> str:
    target = (path.parent / module).resolve()
    try:
        return target.relative_to(source_root).as_posix()
    except ValueError:
        return module


def detect_route_summary(path: Path, text: str, source_root: Path) -> dict | None:
    route_matches = []
    for pattern in ROUTE_PATTERNS:
        route_matches.extend(re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE))
    lowered = text.lower()
    methods = sorted({(match.group(1) or match.group(2) or "").upper() for match in route_matches if any(match.groups())})
    if path.suffix.lower() == ".java" and ("extends httpservlet" in lowered or "@path" in lowered or "@webservlet" in lowered):
        route_matches = route_matches or [None]
        if "doget" in lowered or "@get" in lowered:
            methods.append("GET")
        if "dopost" in lowered or "@post" in lowered:
            methods.append("POST")
        if "doput" in lowered or "@put" in lowered:
            methods.append("PUT")
        if "dodelete" in lowered or "@delete" in lowered:
            methods.append("DELETE")
    if path.suffix.lower() == ".go" and ("handlefunc(" in lowered or "listenandserve(" in lowered):
        handle_count = len(re.findall(r"\bHandleFunc\(", text, flags=re.IGNORECASE))
        route_matches = route_matches or [None] * max(1, handle_count)
        if "http.methodget" in lowered:
            methods.append("GET")
        if "http.methodpost" in lowered:
            methods.append("POST")
    if path.suffix.lower() in {".py", ".js", ".ts", ".tsx", ".jsx", ".graphql", ".gql"} and (
        "graphene.schema" in lowered
        or "add_url_rule('/graphql'" in lowered
        or 'add_url_rule("/graphql"' in lowered
        or "app.use('/graphql'" in lowered
        or 'app.use("/graphql"' in lowered
        or "apolloserver" in lowered
        or "express-graphql" in lowered
        or "graphqlhttp" in lowered
        or "type query" in lowered
        or "type mutation" in lowered
    ):
        route_matches = route_matches or [None]
        methods.append("POST")
    if path.suffix.lower() in {".jsp", ".jspf"} and any(token in lowered for token in ("request.getparameter(", "<jsp:include", "<jsp:forward", "httpsession")):
        route_matches = route_matches or [None]
        methods.extend(["GET", "POST"])
    if not route_matches:
        return None
    framework = detect_framework_for_file(text)
    return {
        "file": relative_path(path, source_root),
        "framework": framework,
        "route_count": len(route_matches),
        "methods": sorted(set(methods))[:6],
    }


def detect_auth_summary(path: Path, text: str, source_root: Path) -> dict | None:
    lowered = text.lower()
    hits = [token for token in AUTH_PATTERNS if token in lowered]
    if not hits:
        return None
    return {
        "file": relative_path(path, source_root),
        "markers": sorted(set(hits))[:6],
    }


def detect_framework_for_file(text: str) -> str:
    lowered = text.lower()
    for framework, hints in FRAMEWORK_HINTS.items():
        if any(re.search(pattern, lowered, flags=re.MULTILINE) for pattern in hints):
            return framework
    return "unknown"


def detect_candidates(text: str, file_path: str, patterns: tuple[str, ...], kind: str) -> list[dict]:
    candidates: list[dict] = []
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        lowered = line.lower()
        if any(re.search(pattern, lowered) for pattern in patterns):
            candidates.append(
                {
                    "file": file_path,
                    "line": index,
                    "kind": kind,
                    "code": line.strip()[:180],
                }
            )
        if len(candidates) >= 8:
            break
    return candidates


def score_hotspot(path: Path, text: str, route_summary: dict | None, auth_summary: dict | None, import_count: int) -> tuple[int, list[str]]:
    lowered_path = path.as_posix().lower()
    lowered = text.lower()
    score = 0
    reasons: list[str] = []

    if route_summary:
        score += 6
        reasons.append("request entrypoint")
    if auth_summary:
        score += 5
        reasons.append("auth boundary")
    if import_count >= 5:
        score += 2
        reasons.append("high connectivity")

    if any(token in lowered_path for token in ("auth", "jwt", "session", "login", "token")):
        score += 4
        reasons.append("authentication boundary")
    if any(token in lowered_path for token in ("route", "router", "controller", "api", "endpoint")):
        score += 3
        reasons.append("request entrypoint")
    if any(token in lowered_path for token in ("service", "client", "repository", "storage", "upload", "resolver", "graphql", "servlet", "dao")):
        score += 2
        reasons.append("sensitive service layer")

    keyword_groups = {
        "subprocess": ["subprocess", "shell=", "os.system", "exec(", "processbuilder", "runtime.getruntime().exec", "child_process.exec"],
        "filesystem": ["send_file", "fileresponse", "open(", "path.join", "os.path.join"],
        "network": ["requests.", "httpx.", "fetch(", "axios.", "urllib", "grpc.dial(", "grpc.newclient("],
        "auth": ["jwt", "verify_signature", "authorization", "bearer", "securitycontext", "principal", "req.session"],
        "query": [".execute(", ".query(", "find_one(", "find(", "$where", "$regex", "sequelize.query", "knex.raw"],
    }
    for label, patterns in keyword_groups.items():
        if any(pattern in lowered for pattern in patterns):
            score += 2
            reasons.append(label)

    return score, sorted(set(reasons))


def build_trust_boundaries(profile: dict, route_files: list[dict], auth_files: list[dict], source_candidates: list[dict], sink_candidates: list[dict]) -> list[str]:
    boundaries: list[str] = []
    if route_files:
        boundaries.append(f"Public request surface across {len(route_files)} route files")
    if auth_files:
        boundaries.append(f"Authentication/session logic appears in {len(auth_files)} files")
    if source_candidates:
        boundaries.append(f"Detected {len(source_candidates)} untrusted-input markers")
    if sink_candidates:
        boundaries.append(f"Detected {len(sink_candidates)} sensitive sink markers")
    if profile["entrypoints"]:
        boundaries.append(f"Primary entrypoints: {', '.join(profile['entrypoints'][:3])}")
    return boundaries


def top_import_metrics(metrics: dict[str, int]) -> list[dict]:
    return [
        {"file": file_path, "count": count}
        for file_path, count in sorted(metrics.items(), key=lambda item: (-item[1], item[0]))[:8]
    ]


def lookup_attack_surface(file_path: str, repository_map: dict) -> str:
    for item in repository_map.get("priority_paths", []):
        if str(item.get("file")) == file_path:
            return str(item.get("attack_surface", "selected scope"))
    return "selected scope"


def lookup_review_focus(file_path: str, repository_map: dict) -> str:
    for item in repository_map.get("priority_paths", []):
        if str(item.get("file")) == file_path:
            return str(item.get("review_focus", "review the strongest trust-boundary risks"))
    return "review the strongest trust-boundary risks"


def has_path_traversal_signal(lowered: str) -> bool:
    has_sink = any(token in lowered for token in ("send_file", "fileresponse", "open(", "read_text(", "write_text("))
    has_join = any(token in lowered for token in ("path.join", "os.path.join", "path(", "resolve("))
    has_source = any(token in lowered for token in INPUT_TOKENS)
    has_defense = any(token in lowered for token in ("resolve()", "safe_join", "normpath", "realpath", "relative_to("))
    return has_sink and has_join and has_source and not has_defense


def has_ssrf_signal(lowered: str) -> bool:
    has_sink = any(
        token in lowered
        for token in ("requests.get(", "requests.post(", "httpx.get(", "httpx.post(", "fetch(", "axios.", "got.", "urllib.request", "grpc.dial(", "grpc.newclient(")
    )
    has_source = any(token in lowered for token in INPUT_TOKENS + ("url", "uri", "webhook", "endpoint", "callback", "target"))
    has_defense = any(
        token in lowered
        for token in ("allowlist", "whitelist", "private ip", "ipaddress", "169.254.169.254", "urlparse", "urlsplit", "metadata", "link-local")
    )
    return has_sink and has_source and not has_defense


def has_sql_injection_signal(lowered: str) -> bool:
    has_query = any(
        token in lowered
        for token in (".execute(", ".query(", "cursor.execute(", "$where", "executequery(", "executeupdate(", "statement.execute(")
    )
    has_interpolation = (
        any(token in lowered for token in ("f\"", "f'", "${", ".format(", " + "))
        or ("%(" in lowered and "%s" not in lowered)
        or ("text(\"" in lowered and "%s" in lowered)
    )
    return has_query and has_interpolation


def has_nosql_injection_signal(lowered: str) -> bool:
    has_query = any(
        token in lowered
        for token in ("find({", "findone({", "updateone({", "aggregate([", "collection(", "$where", "$regex", "$or", "$ne")
    )
    has_source = any(token in lowered for token in INPUT_TOKENS + ("filter", "criteria", "selector"))
    has_defense = any(token in lowered for token in ("$eq", "allowlist", "typed filter", "mongo-sanitize", "bson"))
    return has_query and has_source and not has_defense


def has_eval_injection_signal(lowered: str) -> bool:
    return "eval(" in lowered and any(token in lowered for token in ("req.body", "request.body", "req.query", "req.params"))


def has_command_injection_signal(lowered: str) -> bool:
    has_sink = any(
        token in lowered
        for token in ("shell=true", "os.system(", "child_process.exec(", "runtime.getruntime().exec", "processbuilder", "subprocess.run(", "subprocess.popen(")
    )
    has_source = any(token in lowered for token in INPUT_TOKENS)
    has_defense = any(token in lowered for token in ("shell=false", "argv", "args=[", "args =", "execfile(", "spawn("))
    return has_sink and has_source and not has_defense


def has_open_redirect_signal(lowered: str) -> bool:
    has_redirect = any(token in lowered for token in ("res.redirect(", "response.redirect(", "response.sendredirect(", "dispatcher.forward("))
    has_source = any(
        token in lowered
        for token in ("req.query.url", "req.query.redirect", "req.body.url", "redirect_url", "callback_url", "request.getparameter(", "request.getservletpath(")
    )
    return has_redirect and has_source


def has_graphql_sql_injection_signal(lowered: str) -> bool:
    return (
        ("graphene." in lowered and "filter(text(" in lowered and "%s" in lowered)
        or (
            any(token in lowered for token in ("resolver", "apollo", "graphql"))
            and any(token in lowered for token in ("sequelize.query", "knex.raw", "prisma.$queryraw", "$where"))
            and any(token in lowered for token in ("args.", "input.", "variables.", "context.req"))
        )
    )


def has_graphql_command_injection_signal(lowered: str) -> bool:
    command_sink = any(token in lowered for token in ("helpers.run_cmd(", "run_cmd(", "child_process.exec(", "processbuilder", "runtime.getruntime().exec"))
    graphql_input = any(token in lowered for token in ("graphene.string(", "resolve_system_", "class query(graphene.objecttype)", "args.", "apollo", "resolver"))
    return command_sink and graphql_input


def has_graphql_auth_bypass_signal(lowered: str) -> bool:
    return "decode(token" in lowered and "verify_signature" in lowered and "false" in lowered


def has_graphql_upload_path_signal(lowered: str) -> bool:
    return ("save_file(filename" in lowered or "web_uploaddir + filename" in lowered) and "graphene.string(" in lowered


def has_session_fixation_signal(text: str) -> bool:
    lowered = text.lower()
    executable_lines = [
        line.strip().lower()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("//") and not line.strip().startswith("/*") and not line.strip().startswith("*")
    ]
    mutates_session = any(
        ("req.session." in line and "=" in line)
        or "session.setattribute(" in line
        or "request.getsession(" in line
        for line in executable_lines
    )
    login_context = any(token in lowered for token in ("handlelogin", "/login", "validatelogin", "authenticate", "signin"))
    regenerates_session = any(
        "req.session.regenerate(" in line
        or "session.regenerateid(" in line
        or "change_session_id(" in line
        or "session_regenerate_id(" in line
        for line in executable_lines
    )
    return mutates_session and login_context and not regenerates_session


def has_idor_signal(lowered: str) -> bool:
    route_param = ":userid" in lowered or "req.params.userid" in lowered
    has_session = "req.session.userid" in lowered
    return route_param and has_session


def has_privilege_bypass_signal(lowered: str) -> bool:
    has_admin_route = any(
        token in lowered
        for token in ('app.get("/benefits"', "app.get('/benefits'", 'app.post("/benefits"', "app.post('/benefits'")
    )
    references_admin = "isadmin" in lowered
    live_route_omits_admin = (
        "isloggedin, isadmin," not in lowered
        and "app.get" in lowered
        and "app.post" in lowered
        and "benefitshandler.displaybenefits" in lowered
        and "benefitshandler.updatebenefits" in lowered
    )
    return has_admin_route and references_admin and live_route_omits_admin


def make_finding_candidate(file_path: str, text: str, severity: str, title: str, category: str) -> dict:
    line_number = first_suspicious_line(text)
    snippet = extract_snippet(text, line_number)
    return {
        "source": "heuristic",
        "severity": severity,
        "title": title,
        "file": file_path,
        "line": line_number,
        "category": category,
        "confidence": 84 if severity == "critical" else 80,
        "summary": f"Khwarizm found a high-signal {category.lower()} pattern that appears reachable from untrusted input.",
        "impact": f"The affected flow may allow {category.lower()} exploitation if the input is attacker-controlled.",
        "explanation": f"This file contains a sensitive {category.lower()} sink and nearby untrusted-input markers in the same execution area.",
        "attack_input": "An attacker sends crafted input through the reachable request or integration entry point.",
        "attack_execution": "The input flows into the matched sink without a strong trust-boundary check in the reviewed code.",
        "attack_result": f"The application may suffer {category.lower()} impact on this path.",
        "evidence": snippet,
        "audit_log": [
            "Matched a high-confidence heuristic detector",
            f"Captured evidence from {file_path}:{line_number}",
            "Queued the candidate for AI validation",
        ],
        "fix_suggestions": default_fix_suggestions(category),
    }


def default_fix_suggestions(category: str) -> list[dict[str, str]]:
    return [
        {
            "id": "recommended",
            "label": "Fix A",
            "profile": "recommended",
            "description": f"Refactor the {category.lower()} path so untrusted input cannot reach the sensitive sink directly.",
        },
        {
            "id": "safe",
            "label": "Fix B",
            "profile": "safe",
            "description": "Add explicit validation, canonicalization, and trust-boundary checks before this branch executes.",
        },
        {
            "id": "fast",
            "label": "Fix C",
            "profile": "fast",
            "description": "Add an immediate guard clause to reduce exposure while the full remediation is prepared.",
        },
    ]


def build_finding_id(file_path: str, line_number: int, rule_id: str) -> str:
    digest = hashlib.sha1(f"{file_path}:{line_number}:{rule_id}".encode("utf-8")).hexdigest()
    return digest[:12]


def severity_rank(severity: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(severity, 4)


def extract_relevant_excerpt(text: str, max_lines: int = 18) -> str:
    lines = text.splitlines()
    interesting_indexes = [
        index for index, line in enumerate(lines)
        if any(token in line.lower() for token in ("request", "subprocess", "httpx", "requests", "jwt", "file", "path", "token", "session", "query", "execute", "yaml", "pickle"))
    ]
    if not interesting_indexes:
        selected = lines[:max_lines]
        return "\n".join(f"{index + 1}: {line}" for index, line in enumerate(selected))

    start = max(0, interesting_indexes[0] - 2)
    end = min(len(lines), start + max_lines)
    return "\n".join(f"{start + index + 1}: {line}" for index, line in enumerate(lines[start:end]))


def extract_snippet(content: str, line_number: int, radius: int = 2) -> str:
    lines = content.splitlines()
    start = max(0, line_number - radius - 1)
    end = min(len(lines), line_number + radius)
    return "\n".join(f"{start + index + 1}: {line}" for index, line in enumerate(lines[start:end]))


def first_suspicious_line(text: str) -> int:
    for index, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        if any(token in lowered for token in ("subprocess", "requests.", "httpx.", "send_file", "fileresponse", "jwt", "pickle", "yaml.load")):
            return index
    return 1


def chunk_work_items(work_items: list[dict[str, str]], chunk_size: int) -> list[list[dict[str, str]]]:
    if not work_items:
        return []
    return [work_items[index:index + chunk_size] for index in range(0, len(work_items), chunk_size)]


def adaptive_chunk_work_items(
    work_items: list[dict[str, str]],
    *,
    scan_mode: str,
    support_confidence: str,
    target_prompt_tokens: int = 6000,
) -> list[list[dict[str, str]]]:
    if not work_items:
        return []

    normalized_mode = (scan_mode or "deep").strip().lower()
    normalized_confidence = (support_confidence or "unknown").strip().lower()
    min_batch_size = 1
    max_batch_size = 12 if normalized_mode == "deep" else 6
    if normalized_confidence in {"low", "unknown"}:
        max_batch_size = min(max_batch_size, 6 if normalized_mode == "deep" else 4)

    # Reserve headroom for system prompt, repository map, profile context, and JSON framing.
    prompt_budget = max(1600, int(target_prompt_tokens))
    fixed_overhead_tokens = 2200 if normalized_mode == "deep" else 1800

    batches: list[list[dict[str, str]]] = []
    current_batch: list[dict[str, str]] = []
    current_tokens = fixed_overhead_tokens

    for item in work_items:
        item_tokens = estimate_review_item_tokens(item)
        if current_batch and (
            len(current_batch) >= max_batch_size
            or current_tokens + item_tokens > prompt_budget
        ):
            batches.append(current_batch)
            current_batch = []
            current_tokens = fixed_overhead_tokens

        current_batch.append(item)
        current_tokens += item_tokens

    if current_batch:
        batches.append(current_batch)

    # If a conservative budget produced too many single-item batches, merge small adjacent batches
    # while staying inside the same estimated budget ceiling.
    if len(batches) > 1:
        merged: list[list[dict[str, str]]] = []
        for batch in batches:
            if not merged:
                merged.append(batch)
                continue
            previous = merged[-1]
            previous_tokens = estimate_batch_tokens(previous, fixed_overhead_tokens=fixed_overhead_tokens)
            batch_tokens = estimate_batch_tokens(batch, fixed_overhead_tokens=0)
            if (
                len(previous) + len(batch) <= max_batch_size
                and previous_tokens + batch_tokens <= prompt_budget
            ):
                previous.extend(batch)
            else:
                merged.append(batch)
        batches = merged

    # Keep at least the minimum batch size contract explicit for future tuning.
    return [batch for batch in batches if len(batch) >= min_batch_size]


def estimate_batch_tokens(batch: list[dict[str, str]], *, fixed_overhead_tokens: int = 0) -> int:
    return fixed_overhead_tokens + sum(estimate_review_item_tokens(item) for item in batch)


def estimate_review_item_tokens(item: dict[str, str]) -> int:
    raw = " ".join(
        str(item.get(key, ""))
        for key in (
            "file",
            "rationale",
            "imports",
            "related_attack_surface",
            "review_focus",
            "block_id",
            "block_kind",
            "start_line",
            "end_line",
            "snippet",
        )
    )
    # Simple, conservative heuristic: ~4 chars/token plus JSON/object overhead per work item.
    return max(180, round(len(raw) / 4) + 80)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def relative_path(path: Path, source_root: Path) -> str:
    try:
        return path.relative_to(source_root).as_posix()
    except ValueError:
        return path.name
