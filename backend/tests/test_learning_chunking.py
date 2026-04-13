import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.learning.chunking import (
    ChunkPolicy,
    build_chunk_documents,
    chunk_text,
    reassemble_chunks,
    resolve_overlap_chars,
)


class LearningChunkingTests(unittest.TestCase):
    def test_chunking_uses_zero_overlap_for_code(self):
        policy = ChunkPolicy(chunk_size_chars=64, prose_overlap_chars=16, code_overlap_chars=0)
        overlap = resolve_overlap_chars("code", policy)
        self.assertEqual(overlap, 0)

    def test_chunking_uses_overlap_for_prose(self):
        policy = ChunkPolicy(chunk_size_chars=64, prose_overlap_chars=16, code_overlap_chars=0)
        overlap = resolve_overlap_chars("prose", policy)
        self.assertEqual(overlap, 16)

    def test_reassemble_chunks_restores_text(self):
        text = "A" * 3000 + "B" * 3000 + "C" * 3000
        chunks = chunk_text(text, chunk_size_chars=1024, overlap_chars=256)
        docs = [{"sequence": i, "content_type": "prose", "content": value} for i, value in enumerate(chunks)]
        restored = reassemble_chunks(docs)
        self.assertEqual(restored, text)

    def test_build_chunk_documents_respects_chunk_size(self):
        text = "X" * 25000
        docs, metadata = build_chunk_documents(
            parent_item_id="item-1",
            content=text,
            content_type="code",
            policy=ChunkPolicy(chunk_size_chars=8192),
        )
        self.assertGreater(metadata["chunk_count"], 1)
        self.assertEqual(metadata["chunk_count"], len(docs))
        for document in docs:
            self.assertLessEqual(document["content_length"], 8192)


if __name__ == "__main__":
    unittest.main()

