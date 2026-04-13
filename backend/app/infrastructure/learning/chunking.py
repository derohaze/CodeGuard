from __future__ import annotations

from dataclasses import dataclass

from app.infrastructure.learning.fingerprints import text_checksum
from app.infrastructure.learning.schemas import CHUNK_POLICY_VERSION


MAX_MONGO_DOCUMENT_BYTES = 16 * 1024 * 1024
DEFAULT_CHUNK_SIZE_CHARS = 8 * 1024
DEFAULT_PROSE_OVERLAP_CHARS = 256


@dataclass(frozen=True, slots=True)
class ChunkPolicy:
    chunk_size_chars: int = DEFAULT_CHUNK_SIZE_CHARS
    prose_overlap_chars: int = DEFAULT_PROSE_OVERLAP_CHARS
    code_overlap_chars: int = 0
    policy_version: str = CHUNK_POLICY_VERSION


def resolve_overlap_chars(content_type: str, policy: ChunkPolicy) -> int:
    normalized = content_type.strip().lower()
    if normalized in {"code", "source_code", "diff", "patch"}:
        return policy.code_overlap_chars
    return policy.prose_overlap_chars


def chunk_text(content: str, *, chunk_size_chars: int, overlap_chars: int) -> list[str]:
    if not content:
        return []
    if chunk_size_chars <= 0:
        raise ValueError("chunk_size_chars must be positive.")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be non-negative.")
    if overlap_chars >= chunk_size_chars:
        raise ValueError("overlap_chars must be smaller than chunk_size_chars.")

    chunks: list[str] = []
    step = chunk_size_chars - overlap_chars
    start = 0
    length = len(content)
    while start < length:
        end = min(length, start + chunk_size_chars)
        chunks.append(content[start:end])
        if end >= length:
            break
        start += step
    return chunks


def build_chunk_documents(
    *,
    parent_item_id: str,
    content: str,
    content_type: str,
    policy: ChunkPolicy | None = None,
) -> tuple[list[dict], dict]:
    active_policy = policy or ChunkPolicy()
    overlap = resolve_overlap_chars(content_type, active_policy)
    chunks = chunk_text(
        content,
        chunk_size_chars=active_policy.chunk_size_chars,
        overlap_chars=overlap,
    )
    parent_checksum = text_checksum(content)
    chunk_documents: list[dict] = []
    for index, chunk in enumerate(chunks):
        chunk_documents.append(
            {
                "chunk_id": f"{parent_item_id}:{index}",
                "parent_item_id": parent_item_id,
                "sequence": index,
                "content_type": content_type,
                "content": chunk,
                "content_length": len(chunk),
                "content_checksum": text_checksum(chunk),
                "chunk_policy_version": active_policy.policy_version,
            }
        )
    metadata = {
        "chunk_policy_version": active_policy.policy_version,
        "chunk_size_chars": active_policy.chunk_size_chars,
        "overlap_chars": overlap,
        "chunk_count": len(chunk_documents),
        "parent_checksum": parent_checksum,
        "original_length": len(content),
    }
    return chunk_documents, metadata


def reassemble_chunks(chunk_documents: list[dict]) -> str:
    if not chunk_documents:
        return ""
    ordered = sorted(chunk_documents, key=lambda item: int(item["sequence"]))
    content_type = str(ordered[0].get("content_type", "prose"))
    overlap = resolve_overlap_chars(content_type, ChunkPolicy())
    if overlap <= 0:
        return "".join(str(chunk["content"]) for chunk in ordered)

    parts: list[str] = []
    for index, chunk in enumerate(ordered):
        text = str(chunk["content"])
        if index == 0:
            parts.append(text)
            continue
        parts.append(text[overlap:])
    return "".join(parts)

