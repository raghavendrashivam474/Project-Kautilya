"""Contracts for retrieval results and evidence units in Project Kautilya."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Evidence:
    """A single atomic unit of retrieved evidence.

    Designed to be common across semantic (RAG), structural (KAG), and hybrid retrieval.
    Metadata and origin flags distinguish where and how the evidence was obtained.
    """

    chunk_id: str
    document_id: str
    text: str
    score: float
    retrieval_method: str = "semantic"
    evidence_origin: str = "document/chunk"
    provenance: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert evidence to dictionary representation."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "text": self.text,
            "score": self.score,
            "retrieval_method": self.retrieval_method,
            "evidence_origin": self.evidence_origin,
            "provenance": self.provenance,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class RetrievalResult:
    """Container for the output of a retrieval operation.

    Preserves the query, ranked evidence items, method, and machine-readable execution trace.
    """

    query: str
    evidence: list[Evidence] = field(default_factory=list)
    retrieval_method: str = "semantic"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def top_chunk_ids(self) -> list[str]:
        """Return the chunk IDs in ranked order."""
        return [item.chunk_id for item in self.evidence]

    @property
    def scores(self) -> list[float]:
        """Return the retrieval scores in ranked order."""
        return [item.score for item in self.evidence]

    def to_dict(self) -> dict[str, Any]:
        """Convert retrieval result to dictionary representation for logging/traces."""
        return {
            "query": self.query,
            "retrieval_method": self.retrieval_method,
            "evidence": [item.to_dict() for item in self.evidence],
            "metadata": self.metadata,
        }