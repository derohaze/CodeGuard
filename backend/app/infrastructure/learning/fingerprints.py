from __future__ import annotations

import hashlib
import json
from typing import Any


def text_checksum(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_fingerprint(payload: Any) -> str:
    if isinstance(payload, str):
        canonical = payload
    else:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def bounded_identifier(prefix: str, payload: Any, *, length: int = 24) -> str:
    return f"{prefix}_{stable_fingerprint(payload)[:length]}"

