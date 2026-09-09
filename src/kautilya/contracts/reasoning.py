"""S5 reasoning contracts — deterministic multi-hop query decomposition.

Justification: KnowledgePath represents *discovered* graph paths.
ReasoningPlan represents the *intended* chain derived from question
decomposition, and ReasoningTrace captures per-hop execution outcomes
including explicit failure modes (F1–F5).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Direction(Enum):
    """Traversal direction relative to the current entity."""

    OUTGOING = "outgoing"
    INCOMING = "incoming"


class ReasoningStatus(Enum):
    """Outcome of a reasoning operation."""

    SUCCESS = "success"
    DECOMPOSITION_FAILURE = "F1"
    ENTITY_RESOLUTION_FAILURE = "F2"
    RELATION_FAILURE = "F3"
    TRAVERSAL_FAILURE = "F4"
    EVIDENCE_FAILURE = "F5"


@dataclass(frozen=True)
class ReasoningStep:
    """A single hop in a reasoning plan."""

    relation_type: str
    direction: Direction
    hop_index: int


@dataclass(frozen=True)
class ReasoningPlan:
    """Deterministic decomposition of a compositional query.

    Immutable.  The plan describes *what to look for*, not what was found.
    """

    query: str
    seed_entity_name: str
    steps: tuple[ReasoningStep, ...]

    @property
    def num_hops(self) -> int:
        return len(self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "seed_entity_name": self.seed_entity_name,
            "steps": [
                {
                    "relation_type": s.relation_type,
                    "direction": s.direction.value,
                    "hop_index": s.hop_index,
                }
                for s in self.steps
            ],
        }


@dataclass(frozen=True)
class HopResult:
    """Outcome of executing a single reasoning step against the graph."""

    hop_index: int
    source_entity_id: str
    source_entity_name: str
    relation_type: str
    direction: Direction
    target_entity_id: str | None
    target_entity_name: str | None
    chunk_ids: tuple[str, ...]
    status: ReasoningStatus


@dataclass(frozen=True)
class ReasoningTrace:
    """Full execution trace of a reasoning plan."""

    plan: ReasoningPlan
    hops: tuple[HopResult, ...]
    terminal_entity_name: str | None
    status: ReasoningStatus

    @property
    def is_success(self) -> bool:
        return self.status == ReasoningStatus.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.to_dict(),
            "hops": [
                {
                    "hop_index": h.hop_index,
                    "source": h.source_entity_name,
                    "relation": h.relation_type,
                    "direction": h.direction.value,
                    "target": h.target_entity_name,
                    "chunk_ids": list(h.chunk_ids),
                    "status": h.status.value,
                }
                for h in self.hops
            ],
            "terminal_entity": self.terminal_entity_name,
            "status": self.status.value,
        }
