"""Core domain contracts for Project Kautilya."""

from kautilya.contracts.chunk import Chunk
from kautilya.contracts.document import Document
from kautilya.contracts.entity import Entity
from kautilya.contracts.exploration import ExplorationResult
from kautilya.contracts.knowledge_path import KnowledgePath
from kautilya.contracts.reasoning import (
    Direction,
    HopResult,
    ReasoningPlan,
    ReasoningStatus,
    ReasoningStep,
    ReasoningTrace,
)
from kautilya.contracts.relation import Provenance, Relation
from kautilya.contracts.resolution import Claim, ResolutionResult, ResolutionStatus
from kautilya.contracts.retrieval import Evidence, RetrievalResult
from kautilya.contracts.strategy import RetrievalStrategy, StrategyDecision

__all__ = [
    "Chunk",
    "Claim",
    "Direction",
    "Document",
    "Entity",
    "Evidence",
    "ExplorationResult",
    "HopResult",
    "KnowledgePath",
    "Provenance",
    "ReasoningPlan",
    "ReasoningStatus",
    "ReasoningStep",
    "ReasoningTrace",
    "Relation",
    "ResolutionResult",
    "ResolutionStatus",
    "RetrievalResult",
    "RetrievalStrategy",
    "StrategyDecision",
]
