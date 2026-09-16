"""Contracts for S11 Adaptive Strategy Selection.

Defines the strategy enumeration and decision containers for deterministic
retrieval strategy selection.
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
