"""Core domain contracts for Project Kautilya."""

from kautilya.contracts.chunk import Chunk
from kautilya.contracts.document import Document
from kautilya.contracts.entity import Entity
from kautilya.contracts.exploration import ExplorationResult
from kautilya.contracts.knowledge_path import KnowledgePath
from kautilya.contracts.reasoning import HopPlan, HopResult, ReasoningPlan, ReasoningTrace
from kautilya.contracts.relation import Provenance, Relation
from kautilya.contracts.resolution import Claim, ResolutionResult, ResolutionStatus
from kautilya.contracts.retrieval import Evidence, RetrievalResult

__all__ = [
    "Chunk",
    "Claim",
    "Document",
    "Entity",
    "Evidence",
    "ExplorationResult",
    "HopPlan",
    "HopResult",
    "KnowledgePath",
    "Provenance",
    "ReasoningPlan",
    "ReasoningTrace",
    "Relation",
    "ResolutionResult",
    "ResolutionStatus",
    "RetrievalResult",
]
