"""Contracts for S11/S12 Adaptive Strategy Selection and Evidence Sufficiency.

Defines the strategy enumeration, decision containers, and sufficiency assessment
contracts for deterministic routing and bounded conditional escalation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RetrievalStrategy(str, Enum):
    """Execution strategy chosen for a given query."""

    SEMANTIC = "semantic"
    STRUCTURAL = "structural"
    REASONING = "reasoning"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class StrategyDecision:
    """Deterministic, inspectable outcome of a strategy selection operation."""

    query: str
    selected_strategy: RetrievalStrategy
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert strategy decision to dictionary representation for traces and evaluation."""
        return {
            "query": self.query,
            "selected_strategy": self.selected_strategy.value,
            "reason": self.reason,
            "metadata": self.metadata,
        }


class SufficiencyStatus(str, Enum):
    """Assessment of evidence adequacy after an initial capability execution."""

    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class SufficiencyAssessment:
    """Deterministic, inspectable assessment of whether initial evidence is safe to stop on."""

    status: SufficiencyStatus
    escalation_required: bool
    escalation_strategy: RetrievalStrategy | None = None
    reason: str = ""
    evidence_count: int = 0
    claim_count: int = 0
    reasoning_completed: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert sufficiency assessment to dictionary representation."""
        return {
            "status": self.status.value,
            "escalation_required": self.escalation_required,
            "escalation_strategy": self.escalation_strategy.value if self.escalation_strategy else None,
            "reason": self.reason,
            "evidence_count": self.evidence_count,
            "claim_count": self.claim_count,
            "reasoning_completed": self.reasoning_completed,
            "metadata": self.metadata,
        }
