"""Contracts for S8 Knowledge Exploration.

Defines the core data structures representing the intent, scope,
and inspectable results of an exploration run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kautilya.contracts.entity import Entity
from kautilya.contracts.knowledge_path import KnowledgePath
from kautilya.contracts.reasoning import ReasoningTrace
from kautilya.contracts.retrieval import Evidence


@dataclass(frozen=True)
class ExplorationResult:
    """The deterministic, inspectable outcome of an exploration run."""

    query: str
    objective: str
    seed_entities: tuple[Entity, ...] = field(default_factory=tuple)
    explored_paths: tuple[KnowledgePath, ...] = field(default_factory=tuple)
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    trace: ReasoningTrace | None = None
    status: str = "SUCCESS"  # e.g., SUCCESS, PARTIAL, FAILED, NO_SEEDS
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the ExplorationResult into a JSON-serializable dictionary."""
        return {
            "query": self.query,
            "objective": self.objective,
            "seed_entities": [
                {
                    "id": e.id,
                    "name": e.name,
                    "entity_type": getattr(e, "entity_type", "N/A"),
                    "aliases": list(e.aliases),
                }
                for e in self.seed_entities
            ],
            "explored_paths": [
                {
                    "entities": [ent.name for ent in path.entities]
                    if hasattr(path, "entities")
                    else [],
                    "relations": [rel.relation_type for rel in path.relations]
                    if hasattr(path, "relations")
                    else [],
                }
                for path in self.explored_paths
            ],
            "evidence": [
                {
                    "chunk_id": ev.chunk_id,
                    "document_id": ev.document_id,
                    "score": ev.score,
                    "retrieval_method": ev.retrieval_method,
                    "evidence_origin": ev.evidence_origin,
                }
                for ev in self.evidence
            ],
            "trace": self.trace.to_dict() if self.trace else None,
            "status": self.status,
            "metadata": self.metadata,
        }
