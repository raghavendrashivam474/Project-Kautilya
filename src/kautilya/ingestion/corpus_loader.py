"""Corpus loader — loads raw corpus from disk into typed objects."""
from __future__ import annotations

from pathlib import Path

import yaml

from kautilya.contracts import Document
from kautilya.ingestion.chunker import chunk_document


def load_documents(corpus_dir: Path) -> list[Document]:
    """Load documents from corpus_dir using manifest.yaml."""
    manifest_path = corpus_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Corpus manifest not found: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    documents: list[Document] = []
    docs_dir = corpus_dir / "documents"
    for entry in manifest.get("documents", []):
        source_path = docs_dir / entry["source"]
        if not source_path.exists():
            raise FileNotFoundError(f"Document source missing: {source_path}")
        text = source_path.read_text(encoding="utf-8").strip()
        documents.append(
            Document(
                id=entry["id"],
                title=entry["title"],
                source=entry["source"],
                text=text,
                metadata=entry.get("metadata", {}) or {},
            )
        )
    return documents


def build_chunks(documents: list[Document]) -> list:
    """Chunk every document deterministically."""
    chunks = []
    for doc in documents:
        chunks.extend(chunk_document(doc))
    return chunks
