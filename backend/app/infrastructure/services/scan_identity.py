import hashlib
from pathlib import Path


def normalize_source_path(source_path: str) -> str:
    return str(Path(source_path).expanduser().resolve()).replace("\\", "/").lower()


def build_source_fingerprint(source_path: str, target_type: str) -> str:
    normalized = f"{target_type}:{normalize_source_path(source_path)}"
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
