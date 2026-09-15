"""Contracts for S9 Knowledge Resolution.

Defines data structures representing claims, resolution statuses,
and the deterministic, inspectable outcome of a knowledge resolution run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from kautilya.contracts.retrieval import Evidence


class ResolutionStatus(str, Enum):
    """Classification of the state of knowledge discovered for a query."""

    CONSISTENT = "CONSISTENT"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICTING = "CONFLICTING"
    INSUFFICIENT = "INSUFFICIENT"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class Claim:
    """An atomic factual claim extracted from exploration evidence and paths."""

    subject: str
    predicate: str
    object: str
    evidence_chunk_ids: tuple[str, ...] = field(default_factory=tuple)
    source_document_ids: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert Claim to dictionary representation."""
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "evidence_chunk_ids": list(self.evidence_chunk_ids),
            "source_document_ids": list(self.source_document_ids),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ResolutionResult:
    """The deterministic outcome of resolving knowledge from an ExplorationResult."""

    query: str
    status: ResolutionStatus
    claims: tuple[Claim, ...] = field(default_factory=tuple)
    supporting_evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    conflicting_evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert ResolutionResult to dictionary representation."""
        return {
            "query": self.query,
            "status": self.status.value if isinstance(self.status, ResolutionStatus) else str(self.status),
            "claims": [c.to_dict() for c in self.claims],
            "supporting_evidence": [
                {
                    "chunk_id": ev.chunk_id,
                    "document_id": ev.document_id,
                    "score": ev.score,
                    "retrieval_method": ev.retrieval_method,
                    "evidence_origin": ev.evidence_origin,
                }
                for ev in self.supporting_evidence
            ],
            "conflicting_evidence": [
                {
                    "chunk_id": ev.chunk_id,
                    "document_id": ev.document_id,
                    "score": ev.score,
                    "retrieval_method": ev.retrieval_method,
                    "evidence_origin": ev.evidence_origin,
                }
                for ev in self.conflicting_evidence
            ],
            "rationale": self.rationale,
            "metadata": self.metadata,
        }
