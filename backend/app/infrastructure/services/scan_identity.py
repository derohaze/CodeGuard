import hashlib
from pathlib import Path


def normalize_source_path(source_path: str) -> str:
    return str(Path(source_path).expanduser().resolve()).replace("\\", "/").lower()


def build_source_fingerprint(source_path: str, target_type: str) -> str:
    normalized = f"{target_type}:{normalize_source_path(source_path)}"
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def build_repository_snapshot_fingerprint(source_root: Path, files: list[Path]) -> str:
    digest = hashlib.sha1()
    digest.update(str(source_root).encode("utf-8"))
    digest.update(str(len(files)).encode("utf-8"))

    for path in sorted(files, key=lambda item: item.as_posix().lower()):
        try:
            relative = path.relative_to(source_root).as_posix()
        except ValueError:
            relative = path.name

        digest.update(relative.encode("utf-8"))
        try:
            stat = path.stat()
            digest.update(str(stat.st_size).encode("utf-8"))
            digest.update(str(stat.st_mtime_ns).encode("utf-8"))
        except OSError:
            digest.update(b"missing")

    return digest.hexdigest()[:20]


def build_analysis_cache_key(
    source_fingerprint: str | None,
    snapshot_fingerprint: str | None,
    scan_mode: str,
    target_type: str,
    preset: str,
) -> str:
    normalized = "|".join(
        (
            "analysis-v1",
            (source_fingerprint or "").strip().lower(),
            (snapshot_fingerprint or "").strip().lower(),
            (scan_mode or "deep").strip().lower(),
            (target_type or "folder").strip().lower(),
            (preset or "balanced").strip().lower(),
        )
    )
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:24]
