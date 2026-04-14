from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.exceptions import ExternalAIServiceError


_TEXT_SUFFIX_ALLOWLIST = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rb", ".php", ".cs", ".kt", ".rs",
    ".mjs", ".cjs", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".graphql",
    ".gql", ".sql", ".txt", ".md", ".html", ".css", ".scss", ".xml", ".jsp",
}


def validate_provider_endpoints() -> None:
    settings = get_settings()
    for provider, base_url in (("nvidia", settings.nvidia_base_url),):
        if not base_url:
            continue
        ensure_allowed_outbound_url(base_url, provider=provider)


def ensure_allowed_outbound_url(base_url: str, *, provider: str) -> None:
    parsed = urlparse(base_url.strip())
    if parsed.scheme != "https":
        raise RuntimeError(f"{provider} base URL must use https.")
    if not parsed.hostname:
        raise RuntimeError(f"{provider} base URL must include a hostname.")
    lowered = parsed.hostname.lower()
    forbidden = ("localhost", "127.", "0.0.0.0", "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2", "192.168.")
    if any(lowered.startswith(prefix) for prefix in forbidden):
        raise RuntimeError(f"{provider} base URL points to a disallowed private host.")


def ensure_safe_patch_target(*, source_root: Path, target_file: str) -> Path:
    target_path = (source_root / target_file).resolve()
    if not target_path.exists():
        raise ValueError("Target file does not exist in the selected project scope.")
    try:
        target_path.relative_to(source_root)
    except ValueError as exc:
        raise ValueError("Target file escapes the selected project scope.") from exc
    if target_path.is_dir():
        raise ValueError("Target patch scope must be a file, not a directory.")
    if target_path.suffix.lower() not in _TEXT_SUFFIX_ALLOWLIST:
        raise ValueError("Target file type is not approved for automatic local patching.")
    return target_path


def build_write_scope_note(target_file: str) -> str:
    return f"Local write scope is limited to {target_file} within the selected project."


def build_network_policy_note() -> str:
    return "Patch apply, verify, and rollback perform no outbound network actions."


def sanitize_runtime_error(exc: Exception, *, operation: str) -> str:
    if isinstance(exc, ExternalAIServiceError):
        if operation == "scan":
            return "Khwarizm could not complete the scan because the configured AI runtime was temporarily unavailable. Retry shortly."
        if operation == "remediation":
            return "Khwarizm could not complete remediation analysis because the AI runtime was temporarily unavailable. Retry shortly."
        return "Khwarizm could not complete the requested AI operation because the runtime was temporarily unavailable. Retry shortly."
    return "Khwarizm could not complete the requested operation. Retry shortly."
