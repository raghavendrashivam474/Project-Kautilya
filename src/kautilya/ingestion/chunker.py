"""Deterministic paragraph-based chunker.

S1 uses a simple, reproducible strategy: split document text on blank lines,
strip whitespace, and assign a stable sequence ID.
"""

from __future__ import annotations

from kautilya.contracts import Chunk, Document


def chunk_document(document: Document) -> list[Chunk]:
    """Split a Document into paragraph-level Chunks with stable IDs."""
    paragraphs = [p.strip() for p in document.text.split("\n\n") if p.strip()]
    if not paragraphs:
        # Fall back to a single chunk containing the whole text.
        paragraphs = [document.text.strip()]

    chunks: list[Chunk] = []
    doc_num = document.id.split("_")[-1]
    for i, para in enumerate(paragraphs, start=1):
        chunk_id = f"chunk_{doc_num}_{i:03d}"
        chunks.append(Chunk(id=chunk_id, document_id=document.id, text=para, sequence=i))
    return chunks
