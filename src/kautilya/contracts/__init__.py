"""Core domain contracts for Project Kautilya."""

from kautilya.contracts.chunk import Chunk
from kautilya.contracts.document import Document
from kautilya.contracts.entity import Entity
from kautilya.contracts.relation import Provenance, Relation
from kautilya.contracts.retrieval import Evidence, RetrievalResult

__all__ = [
    "Chunk",
    "Document",
    "Entity",
    "Evidence",
    "Provenance",
    "Relation",
    "RetrievalResult",
]